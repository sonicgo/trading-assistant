"""
Market Data Service

On-demand sync functionality for fetching and storing market prices.
Uses batch fetching to minimize API calls and avoid rate limits.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    incremental: bool = False,
) -> SyncResult:
    """
    Sync market prices for all unique listings held in a portfolio.
    
    Queries the portfolio's current holdings (via HoldingSnapshot),
    fetches latest prices from Yahoo Finance in a single batch request,
    and saves them as PricePoint records.
    
    Args:
        db: SQLAlchemy Session
        portfolio_id: UUID of portfolio to sync
        incremental: If True, skip listings with prices within last 24 hours
        
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
    
    # Build mapping of ticker -> listing_id for all holdings
    ticker_to_listing: dict[str, str] = {}
    listings: list[InstrumentListing] = []
    
    for row in holdings:
        listing = row.InstrumentListing
        ticker = listing.ticker
        listing_id_str = str(listing.listing_id)
        
        # Only add unique tickers
        if ticker not in ticker_to_listing:
            ticker_to_listing[ticker] = listing_id_str
            listings.append(listing)
    
    # If incremental mode, filter out listings with recent prices (within 24 hours)
    if incremental:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Get listing_ids that have recent prices
        recent_listing_ids = {
            str(pp.listing_id) for pp in
            db.query(PricePoint.listing_id)
            .filter(
                PricePoint.listing_id.in_([uuid.UUID(lid) for lid in ticker_to_listing.values()]),
                PricePoint.as_of >= cutoff_time,
            )
            .distinct()
            .all()
        }
        
        # Filter the ticker_to_listing dict
        filtered_ticker_to_listing = {
            ticker: listing_id
            for ticker, listing_id in ticker_to_listing.items()
            if listing_id not in recent_listing_ids
        }
        
        if not filtered_ticker_to_listing:
            return SyncResult(
                portfolio_id=portfolio_id,
                total_listings=len(listings),
                prices_fetched=0,
                prices_inserted=0,
                errors=[],
            )
        
        ticker_to_listing = filtered_ticker_to_listing
    
    unique_tickers = list(ticker_to_listing.keys())
    prices_inserted = 0
    prices_fetched = 0
    
    try:
        # Fetch all prices in a single batch request
        price_data = await asyncio.to_thread(
            adapter.fetch_prices_batch,
            unique_tickers,
        )
        
        # Process the batch results
        for ticker, (price, as_of, currency) in price_data.items():
            listing_id_str = ticker_to_listing.get(ticker)
            if not listing_id_str:
                continue
            
            prices_fetched += 1
            
            stmt = (
                insert(PricePoint)
                .values(
                    price_point_id=uuid.uuid4(),
                    listing_id=uuid.UUID(listing_id_str),
                    as_of=as_of,
                    price=price,
                    currency=currency,
                    is_close=True,
                    source_id=adapter.source_id,
                    raw={"ticker": ticker, "batch_fetch": True},
                )
                .on_conflict_do_nothing(
                    index_elements=["listing_id", "as_of", "source_id", "is_close"]
                )
            )
            
            result = db.execute(stmt)
            if result.rowcount > 0:
                prices_inserted += 1
        
        # Report tickers that failed to fetch
        failed_tickers = set(unique_tickers) - set(price_data.keys())
        for ticker in failed_tickers:
            errors.append(f"No price data returned for {ticker}")
            
    except Exception as exc:
        errors.append(f"Batch fetch failed: {str(exc)}")
    
    return SyncResult(
        portfolio_id=portfolio_id,
        total_listings=len(listings),
        prices_fetched=prices_fetched,
        prices_inserted=prices_inserted,
        errors=errors,
    )
