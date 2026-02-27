"""
Registry API endpoints — Instruments and Listings.

Critical mapping rule (LLD-2 §4.3):
  API:  trading_currency (GBP/USD/EUR) + price_scale (MAJOR/MINOR)
  DB:   trading_currency (stored as-is) + quote_scale (GBX/GBP/USD/…)

  if trading_currency == "GBP" and price_scale == "MINOR":
      quote_scale = "GBX"
  else:
      quote_scale = trading_currency
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api import deps
from app.domain import models
from app.schemas import registry as schemas

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_quote_scale(trading_currency: str, price_scale: str) -> str:
    """Map API (trading_currency + price_scale) → DB quote_scale."""
    if trading_currency.upper() == "GBP" and price_scale == "MINOR":
        return "GBX"
    return trading_currency.upper()


# ===========================================================================
# Instruments
# ===========================================================================

@router.get("/instruments", response_model=schemas.InstrumentsPage)
def list_instruments(
    db: deps.SessionDep,
    _user: deps.CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, description="Free-text filter on instrument name"),
    isin: str | None = Query(default=None, description="Exact ISIN match"),
):
    """List instruments with optional free-text and ISIN filters."""
    query = db.query(models.Instrument)
    if isin:
        query = query.filter(models.Instrument.isin == isin.upper())
    if q:
        query = query.filter(models.Instrument.name.ilike(f"%{q}%"))

    total = query.count()
    items = query.order_by(models.Instrument.created_at.desc()).offset(offset).limit(limit).all()

    return schemas.InstrumentsPage(items=items, limit=limit, offset=offset, total=total)


@router.post("/instruments", response_model=schemas.InstrumentResponse, status_code=201)
def create_instrument(
    data: schemas.InstrumentCreate,
    db: deps.SessionDep,
    _user: deps.CurrentUser,
):
    """Create a new instrument (ISIN must be unique)."""
    existing = db.query(models.Instrument).filter(
        models.Instrument.isin == data.isin.upper()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Instrument with ISIN {data.isin!r} already exists",
        )

    new_instrument = models.Instrument(
        isin=data.isin.upper(),
        name=data.name,
        instrument_type=data.instrument_type,
    )
    db.add(new_instrument)
    db.commit()
    db.refresh(new_instrument)
    return new_instrument


@router.patch("/instruments/{instrument_id}", response_model=schemas.InstrumentResponse)
def update_instrument(
    instrument_id: UUID,
    data: schemas.InstrumentUpdate,
    db: deps.SessionDep,
    _user: deps.CurrentUser,
):
    """Partially update an instrument (PATCH semantics)."""
    instrument = (
        db.query(models.Instrument)
        .filter(models.Instrument.instrument_id == instrument_id)
        .first()
    )
    if not instrument:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(instrument, field, value)

    db.commit()
    db.refresh(instrument)
    return instrument


# ===========================================================================
# Listings
# ===========================================================================

@router.get("/listings", response_model=schemas.ListingsPage)
def list_listings(
    db: deps.SessionDep,
    _user: deps.CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    instrument_id: UUID | None = Query(default=None),
    exchange: str | None = Query(default=None),
    ticker: str | None = Query(default=None),
):
    """List listings with optional filters."""
    query = db.query(models.InstrumentListing)
    if instrument_id:
        query = query.filter(models.InstrumentListing.instrument_id == instrument_id)
    if exchange:
        query = query.filter(models.InstrumentListing.exchange.ilike(exchange))
    if ticker:
        query = query.filter(models.InstrumentListing.ticker.ilike(ticker))

    total = query.count()
    items = query.order_by(models.InstrumentListing.created_at.desc()).offset(offset).limit(limit).all()

    return schemas.ListingsPage(
        items=[schemas.ListingResponse.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/listings", response_model=schemas.ListingResponse, status_code=201)
def create_listing(
    data: schemas.ListingCreate,
    db: deps.SessionDep,
    _user: deps.CurrentUser,
):
    """
    Create a listing.

    Critical mapping: GBP + MINOR → quote_scale = GBX.
    The `trading_currency` field is stored as-is; `quote_scale` is derived.
    """
    # Verify parent instrument exists
    instrument = db.query(models.Instrument).filter(
        models.Instrument.instrument_id == data.instrument_id
    ).first()
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Instrument {data.instrument_id} not found",
        )

    quote_scale = _derive_quote_scale(data.trading_currency, data.price_scale.value)

    new_listing = models.InstrumentListing(
        instrument_id=data.instrument_id,
        ticker=data.ticker.upper(),
        exchange=data.exchange.upper(),
        trading_currency=data.trading_currency.upper(),
        quote_scale=quote_scale,
        is_primary=data.is_primary,
    )
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    return schemas.ListingResponse.model_validate(new_listing)


@router.patch("/listings/{listing_id}", response_model=schemas.ListingResponse)
def update_listing(
    listing_id: UUID,
    data: schemas.ListingUpdate,
    db: deps.SessionDep,
    _user: deps.CurrentUser,
):
    """
    Partially update a listing (PATCH semantics).

    When `trading_currency` or `price_scale` is supplied, `quote_scale` is
    recomputed to keep the DB consistent with the GBP+MINOR→GBX rule.
    """
    listing = (
        db.query(models.InstrumentListing)
        .filter(models.InstrumentListing.listing_id == listing_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    updates = data.model_dump(exclude_unset=True)

    # Simple field updates
    if "ticker" in updates:
        listing.ticker = updates["ticker"].upper()
    if "exchange" in updates:
        listing.exchange = updates["exchange"].upper()
    if "is_primary" in updates:
        listing.is_primary = updates["is_primary"]

    # Re-derive quote_scale if currency or scale changes
    if "trading_currency" in updates or "price_scale" in updates:
        new_currency = updates.get("trading_currency", listing.trading_currency)
        new_scale_enum = updates.get("price_scale")
        if new_scale_enum is not None:
            # It's a PriceScale enum instance
            new_scale_str = new_scale_enum.value if hasattr(new_scale_enum, "value") else str(new_scale_enum)
        else:
            # Derive current scale from stored quote_scale
            new_scale_str = "MINOR" if listing.quote_scale == "GBX" else "MAJOR"

        listing.trading_currency = new_currency.upper()
        listing.quote_scale = _derive_quote_scale(new_currency, new_scale_str)

    db.commit()
    db.refresh(listing)
    return schemas.ListingResponse.model_validate(listing)
