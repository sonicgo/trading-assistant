"""Snapshot API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api import deps
from app.domain import models
from app.schemas import ledger as schemas
from app.services.snapshots import get_or_create_cash_snapshot, get_or_create_holding_snapshot

router = APIRouter()


@router.get(
    "/{portfolio_id}/snapshots/cash",
    response_model=schemas.CashSnapshotResponse,
)
def get_cash_snapshot(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Get current cash snapshot for a portfolio (tenancy-checked)."""
    snapshot = get_or_create_cash_snapshot(db, portfolio_id)
    
    return schemas.CashSnapshotResponse(
        portfolio_id=snapshot.portfolio_id,
        balance_gbp=snapshot.balance_gbp,
        updated_at=snapshot.updated_at,
        last_entry_id=snapshot.last_entry_id,
        version_no=int(snapshot.version_no),
    )


@router.get(
    "/{portfolio_id}/snapshots/holdings",
    response_model=schemas.HoldingSnapshotListResponse,
)
def get_holding_snapshots(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Get current holding snapshots for a portfolio (tenancy-checked)."""
    holdings = (
        db.query(models.HoldingSnapshot)
        .filter(models.HoldingSnapshot.portfolio_id == portfolio_id)
        .all()
    )
    
    total_book_cost = sum(h.book_cost_gbp for h in holdings)
    
    return schemas.HoldingSnapshotListResponse(
        portfolio_id=portfolio_id,
        holdings=[
            schemas.HoldingSnapshotResponse(
                portfolio_id=h.portfolio_id,
                listing_id=h.listing_id,
                quantity=h.quantity,
                book_cost_gbp=h.book_cost_gbp,
                avg_cost_gbp=h.avg_cost_gbp,
                updated_at=h.updated_at,
                last_entry_id=h.last_entry_id,
                version_no=int(h.version_no),
            )
            for h in holdings
        ],
        total_book_cost_gbp=total_book_cost,
    )
