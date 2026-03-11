"""
Market Data Service

On-demand sync functionality for fetching and storing market prices.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.domain.models import (
    PricePoint,
    InstrumentListing,
    HoldingSnapshot,
)
from app.services.providers.yfinance_adapter import YFinanceAdapter


@dataclass
class SyncResult:
    """Result of portfolio price sync operation."""
    
    portfolio_id: str
    total_listings: int
    prices_fetched: int
    prices_inserted: int
    errors: list[str] = field(default_factory=list)
    
    
async def sync_portfolio_prices(
    db: Session,
    portfolio_id: str,
    *,
    rate_limit_delay: float = 1.5,
) -> SyncResult:
    """
    Sync market prices for all unique listings held in a portfolio.
    
    Queries the portfolio's current holdings (via HoldingSnapshot),
    fetches latest prices from Yahoo Finance with rate limiting,
    and saves them as PricePoint records.
    
    Args:
        db: SQLAlchemy Session
        portfolio_id: UUID of portfolio to sync
        rate_limit_delay: Seconds to wait between API calls (default 1.5)
        
    Returns:
        SyncResult with counts and any errors
    """
    adapter = YFinanceAdapter()
    errors: list[str] = []
    
    holdings = (
        db.query(HoldingSnapshot, InstrumentListing)
        .join(
            InstrumentListing,
            HoldingSnapshot.listing_id == InstrumentListing.listing_id,
        )
        .filter(
            HoldingSnapshot.portfolio_id == portfolio_id,
            HoldingSnapshot.quantity > 0,
        )
        .all()
    )
    
    if not holdings:
        return SyncResult(
            portfolio_id=portfolio_id,
            total_listings=0,
            prices_fetched=0,
            prices_inserted=0,
            errors=["No holdings found in portfolio"],
        )
    
    listings: list[InstrumentListing] = [row.InstrumentListing for row in holdings]
    prices_inserted = 0
    prices_fetched = 0
    
    for i, listing in enumerate(listings):
        ticker = listing.ticker
        listing_id_str = str(listing.listing_id)
        
        try:
            quotes = await adapter.fetch_prices(
                [ticker],
                want_close=True,
                want_intraday=False,
            )
            
            if not quotes:
                errors.append(f"No price data for {ticker}")
                continue
                
            quote = quotes[0]
            prices_fetched += 1
            
            stmt = (
                insert(PricePoint)
                .values(
                    price_point_id=uuid.uuid4(),
                    listing_id=uuid.UUID(listing_id_str),
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
                
        except Exception as exc:
            errors.append(f"Failed to fetch {ticker}: {str(exc)}")
        
        if i < len(listings) - 1:
            await asyncio.sleep(rate_limit_delay)
    
    return SyncResult(
        portfolio_id=portfolio_id,
        total_listings=len(listings),
        prices_fetched=prices_fetched,
        prices_inserted=prices_inserted,
        errors=errors,
    )
