"""
Portfolio API endpoints.

Constituent bulk-upsert semantics (PUT /portfolios/{id}/constituents):
  1. If replace_missing=true, delete all existing constituents NOT in the payload.
  2. For each item in the payload:
     a. Enforce one-listing-per-sleeve: if another listing already occupies the
        requested sleeve_code in this portfolio, evict it first.
     b. Upsert by PK (portfolio_id, listing_id).
  3. Commit atomically.

Tenancy is enforced on every scoped endpoint via `require_portfolio_access`.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.domain import models
from app.schemas import portfolio as schemas

router = APIRouter()


# ===========================================================================
# Portfolios
# ===========================================================================

@router.get("", response_model=list[schemas.PortfolioResponse])
def list_portfolios(db: deps.SessionDep, user: deps.CurrentUser):
    """Return all portfolios owned by the current user."""
    return (
        db.query(models.Portfolio)
        .filter(models.Portfolio.owner_user_id == user.user_id)
        .order_by(models.Portfolio.created_at.desc())
        .all()
    )


@router.post("", response_model=schemas.PortfolioResponse, status_code=201)
def create_portfolio(
    data: schemas.PortfolioCreate,
    db: deps.SessionDep,
    user: deps.CurrentUser,
):
    """Create a new portfolio owned by the current user."""
    new_portfolio = models.Portfolio(
        name=data.name,
        base_currency=data.base_currency.upper(),
        tax_profile=data.tax_profile.value,
        broker=data.broker,
        owner_user_id=user.user_id,
        is_enabled=True,
    )
    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)
    return new_portfolio


@router.get("/{portfolio_id}", response_model=schemas.PortfolioResponse)
def get_portfolio(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Get a single portfolio (tenancy-checked)."""
    return portfolio


@router.patch("/{portfolio_id}", response_model=schemas.PortfolioResponse)
def update_portfolio(
    data: schemas.PortfolioUpdate,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
):
    """Partially update a portfolio (PATCH semantics, tenancy-checked)."""
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        # Unwrap Enum instances to their string value before setting on ORM object
        setattr(portfolio, field, value.value if hasattr(value, "value") else value)

    db.commit()
    db.refresh(portfolio)
    return portfolio


# ===========================================================================
# Constituents
# ===========================================================================

@router.get(
    "/{portfolio_id}/constituents",
    response_model=list[schemas.PortfolioConstituentResponse],
)
def get_portfolio_constituents(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
):
    """List all constituents for a portfolio (tenancy-checked)."""
    return (
        db.query(models.PortfolioConstituent)
        .filter(models.PortfolioConstituent.portfolio_id == portfolio.portfolio_id)
        .order_by(models.PortfolioConstituent.created_at)
        .all()
    )


@router.put(
    "/{portfolio_id}/constituents",
    response_model=schemas.ConstituentBulkUpsertResponse,
)
def bulk_upsert_constituents(
    data: schemas.ConstituentBulkUpsert,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
):
    """
    Bulk upsert constituents for a portfolio (tenancy-checked).

    Semantics:
    - Transactional: all changes applied atomically.
    - One listing per sleeve per portfolio: if a different listing already
      occupies the target sleeve, the old occupant is evicted first.
    - replace_missing=true: any constituent NOT in the payload is deleted.
    """
    portfolio_id: UUID = portfolio.portfolio_id

    # ── Step 1: delete stale rows (replace_missing semantics) ──────────────
    if data.replace_missing:
        incoming_listing_ids = {item.listing_id for item in data.items}
        (
            db.query(models.PortfolioConstituent)
            .filter(
                models.PortfolioConstituent.portfolio_id == portfolio_id,
                models.PortfolioConstituent.listing_id.notin_(incoming_listing_ids),
            )
            .delete(synchronize_session="fetch")
        )

    # ── Step 2: upsert each item ────────────────────────────────────────────
    for item in data.items:
        # Verify the listing actually exists
        listing = db.query(models.InstrumentListing).filter(
            models.InstrumentListing.listing_id == item.listing_id
        ).first()
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Listing {item.listing_id} not found",
            )

        # Verify the sleeve code exists
        sleeve = db.query(models.Sleeve).filter(
            models.Sleeve.sleeve_code == item.sleeve_code
        ).first()
        if not sleeve:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Sleeve code {item.sleeve_code!r} not found",
            )

        # Enforce one listing per sleeve per portfolio:
        # If another listing (≠ this one) already occupies the target sleeve, evict it.
        conflicting = (
            db.query(models.PortfolioConstituent)
            .filter(
                models.PortfolioConstituent.portfolio_id == portfolio_id,
                models.PortfolioConstituent.sleeve_code == item.sleeve_code,
                models.PortfolioConstituent.listing_id != item.listing_id,
            )
            .first()
        )
        if conflicting:
            db.delete(conflicting)
            db.flush()

        # Upsert by PK (portfolio_id, listing_id)
        existing = (
            db.query(models.PortfolioConstituent)
            .filter_by(portfolio_id=portfolio_id, listing_id=item.listing_id)
            .first()
        )
        if existing:
            existing.sleeve_code = item.sleeve_code
            existing.is_monitored = item.is_monitored
        else:
            db.add(
                models.PortfolioConstituent(
                    portfolio_id=portfolio_id,
                    listing_id=item.listing_id,
                    sleeve_code=item.sleeve_code,
                    is_monitored=item.is_monitored,
                )
            )

    db.commit()
    return schemas.ConstituentBulkUpsertResponse(updated_count=len(data.items))
