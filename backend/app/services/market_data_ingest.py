"""
Market Data Ingestion Pipeline

Fetches prices and FX rates for a portfolio's monitored constituents
and writes them idempotently to the database.

CRITICAL: Uses externally-managed DB sessions (NOT FastAPI Depends).
Caller (worker) is responsible for commit/rollback.
"""
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.domain.models import (
    PricePoint,
    FxRate,
    PortfolioConstituent,
    InstrumentListing,
    Portfolio,
)
from app.services.market_data_adapter import MarketDataAdapter, PriceQuote, FxQuote


@dataclass
class IngestResult:
    """Result of ingestion operation."""

    run_id: str                          # UUID for this ingestion run
    portfolio_id: str
    job_id: str
    price_quotes: list[PriceQuote]
    fx_quotes: list[FxQuote]
    listings: list[InstrumentListing]    # Metadata for DQ gate
    prices_inserted: int
    fx_inserted: int
    errors: list[str] = field(default_factory=list)


async def ingest_prices_for_portfolio(
    db: Session,
    adapter: MarketDataAdapter,
    portfolio_id: str,
    job_id: str,
    *,
    want_close: bool = True,
    want_intraday: bool = True,
) -> IngestResult:
    """
    Ingest market data for a portfolio's monitored constituents.

    CRITICAL: Uses externally-provided db session (worker manages lifecycle).
    All writes are idempotent (ON CONFLICT DO NOTHING).

    Args:
        db: SQLAlchemy Session (provided by worker, NOT FastAPI Depends)
        adapter: MarketDataAdapter implementation (e.g., MockProvider)
        portfolio_id: UUID of portfolio to ingest for
        job_id: Job ID from queue for correlation
        want_close: Whether to fetch EOD close prices
        want_intraday: Whether to fetch intraday prices

    Returns:
        IngestResult with all fetched quotes and metadata
    """
    run_id = str(uuid.uuid4())
    errors: list[str] = []

    # 1. Load portfolio and verify it exists
    portfolio = db.query(Portfolio).filter_by(portfolio_id=portfolio_id).first()
    if not portfolio:
        raise ValueError(f"Portfolio {portfolio_id} not found")

    # 2. Load monitored constituents + their listings
    constituents = (
        db.query(PortfolioConstituent, InstrumentListing)
        .join(
            InstrumentListing,
            PortfolioConstituent.listing_id == InstrumentListing.listing_id,
        )
        .filter(
            PortfolioConstituent.portfolio_id == portfolio_id,
            PortfolioConstituent.is_monitored == True,  # noqa: E712
        )
        .all()
    )

    if not constituents:
        return IngestResult(
            run_id=run_id,
            portfolio_id=portfolio_id,
            job_id=job_id,
            price_quotes=[],
            fx_quotes=[],
            listings=[],
            prices_inserted=0,
            fx_inserted=0,
            errors=["No monitored constituents found"],
        )

    listings: list[InstrumentListing] = [row.InstrumentListing for row in constituents]
    listing_ids: list[str] = [str(listing.listing_id) for listing in listings]

    # 3. Determine FX pairs needed (portfolio base currency vs. listing currencies)
    base_currency: str = portfolio.base_currency
    trading_currencies = {listing.trading_currency for listing in listings}
    fx_pairs = [(base_currency, ccy) for ccy in trading_currencies if ccy != base_currency]

    # 4. Fetch prices from adapter
    try:
        price_quotes = await adapter.fetch_prices(
            listing_ids,
            want_close=want_close,
            want_intraday=want_intraday,
        )
    except Exception as exc:
        errors.append(f"Price fetch failed: {exc}")
        price_quotes = []

    # 5. Fetch FX rates from adapter
    try:
        fx_quotes = await adapter.fetch_fx_rates(fx_pairs) if fx_pairs else []
    except Exception as exc:
        errors.append(f"FX fetch failed: {exc}")
        fx_quotes = []

    # 6. Write price_points IDEMPOTENTLY (ON CONFLICT DO NOTHING)
    prices_inserted = 0
    for quote in price_quotes:
        stmt = (
            insert(PricePoint)
            .values(
                price_point_id=uuid.uuid4(),
                listing_id=quote.listing_id,
                as_of=quote.as_of,
                price=Decimal(quote.price),
                currency=quote.currency,
                is_close=quote.is_close,
                source_id=adapter.source_id,
                raw=quote.raw,
            )
            .on_conflict_do_nothing(
                index_elements=["listing_id", "as_of", "source_id", "is_close"]
            )
        )
        result = db.execute(stmt)
        if result.rowcount > 0:
            prices_inserted += 1

    # 7. Write fx_rates IDEMPOTENTLY (ON CONFLICT DO NOTHING)
    fx_inserted = 0
    for fx in fx_quotes:
        stmt = (
            insert(FxRate)
            .values(
                fx_rate_id=uuid.uuid4(),
                base_ccy=fx.base_ccy,
                quote_ccy=fx.quote_ccy,
                as_of=fx.as_of,
                rate=Decimal(fx.rate),
                source_id=adapter.source_id,
            )
            .on_conflict_do_nothing(
                index_elements=["base_ccy", "quote_ccy", "as_of", "source_id"]
            )
        )
        result = db.execute(stmt)
        if result.rowcount > 0:
            fx_inserted += 1

    # Note: Caller (worker) handles commit/rollback — do NOT commit here.

    return IngestResult(
        run_id=run_id,
        portfolio_id=portfolio_id,
        job_id=job_id,
        price_quotes=price_quotes,
        fx_quotes=fx_quotes,
        listings=listings,
        prices_inserted=prices_inserted,
        fx_inserted=fx_inserted,
        errors=errors,
    )
