#!/usr/bin/env python3
"""
Sync Market Data Script

Fetches latest EOD prices from Yahoo Finance for all listings
and saves them to the database as PricePoint records.

Usage:
    cd backend && python scripts/sync_market_data.py
"""
import os
import sys
import uuid
import time
import asyncio
from decimal import Decimal
from datetime import datetime, timezone

# Add the parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.services.providers.yfinance_adapter import YFinanceAdapter
from app.domain.models import PricePoint, InstrumentListing

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Rate limiting delay (seconds)
RATE_LIMIT_DELAY = 1.5


async def fetch_and_save_price(
    session, adapter: YFinanceAdapter, listing: InstrumentListing
) -> tuple[bool, str]:
    """
    Fetch price for a single listing and save to database.
    
    Returns:
        (success: bool, message: str)
    """
    ticker = listing.ticker
    listing_id = str(listing.listing_id)
    
    try:
        # Fetch price using YFinanceAdapter (passing ticker as listing_id)
        quotes = await adapter.fetch_prices(
            [ticker],  # Adapter uses ticker directly, applies .L suffix internally
            want_close=True,
            want_intraday=False,
        )
        
        if not quotes:
            return False, f"No price data returned for {ticker}"
        
        quote = quotes[0]
        
        # Create PricePoint record
        price_point = PricePoint(
            price_point_id=uuid.uuid4(),
            listing_id=uuid.UUID(listing_id),
            as_of=quote.as_of,
            price=Decimal(quote.price),
            currency=quote.currency,
            is_close=quote.is_close,
            source_id=adapter.source_id,
            raw=quote.raw,
        )
        
        # Use ON CONFLICT DO NOTHING for idempotency
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = (
            insert(PricePoint)
            .values(
                price_point_id=price_point.price_point_id,
                listing_id=price_point.listing_id,
                as_of=price_point.as_of,
                price=price_point.price,
                currency=price_point.currency,
                is_close=price_point.is_close,
                source_id=price_point.source_id,
                raw=price_point.raw,
            )
            .on_conflict_do_nothing(
                index_elements=["listing_id", "as_of", "source_id", "is_close"]
            )
        )
        
        result = session.execute(stmt)
        
        if result.rowcount > 0:
            return True, f"Saved {ticker}: {quote.price} {quote.currency} @ {quote.as_of}"
        else:
            return True, f"Skipped {ticker}: Price already exists for this timestamp"
            
    except Exception as e:
        return False, f"Failed {ticker}: {str(e)}"


async def sync_market_data():
    """Main sync function."""
    print("=" * 60)
    print("MARKET DATA SYNC")
    print("=" * 60)
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    adapter = YFinanceAdapter()
    session = SessionLocal()
    
    try:
        # Target specific test tickers first
        TARGET_TICKERS = ['VWRP', 'CSH2', 'IGL5', 'SEMI', 'WLDS', 'XWES', 'XWHS']
        
        # Query specific listings by ticker
        query = text("""
            SELECT DISTINCT l.listing_id, l.ticker, l.exchange, l.trading_currency
            FROM listing l
            WHERE l.ticker = ANY(:tickers)
            ORDER BY l.ticker
        """)
        
        result = session.execute(query, {"tickers": TARGET_TICKERS})
        rows = result.fetchall()
        
        if not rows:
            print("No target tickers found. Trying monitored portfolio constituents...")
            
            # Fallback: Get monitored listings from portfolios
            query = text("""
                SELECT DISTINCT l.listing_id, l.ticker, l.exchange, l.trading_currency
                FROM listing l
                JOIN portfolio_constituent pc ON l.listing_id = pc.listing_id
                WHERE pc.is_monitored = true
                ORDER BY l.ticker
            """)
            result = session.execute(query)
            rows = result.fetchall()
        
        if not rows:
            print("No monitored listings found. Trying all listings...")
            
            # Final fallback: get all listings
            query = text("""
                SELECT listing_id, ticker, exchange, trading_currency
                FROM listing
                ORDER BY ticker
            """)
            result = session.execute(query)
            rows = result.fetchall()
        
        if not rows:
            print("ERROR: No listings found in database.")
            return
        
        print(f"Found {len(rows)} listings to sync:\n")
        
        # Convert rows to InstrumentListing-like objects
        listings = []
        for row in rows:
            listing = InstrumentListing(
                listing_id=row.listing_id,
                ticker=row.ticker,
                exchange=row.exchange,
                trading_currency=row.trading_currency,
            )
            listings.append(listing)
            print(f"  - {row.ticker} ({row.exchange})")
        
        print()
        print("=" * 60)
        print("FETCHING PRICES FROM YAHOO FINANCE")
        print("=" * 60)
        print()
        
        success_count = 0
        error_count = 0
        
        for i, listing in enumerate(listings, 1):
            print(f"[{i}/{len(listings)}] ", end="", flush=True)
            
            success, message = await fetch_and_save_price(session, adapter, listing)
            print(message)
            
            if success:
                success_count += 1
            else:
                error_count += 1
            
            # Rate limiting: wait between requests (except for the last one)
            if i < len(listings):
                time.sleep(RATE_LIMIT_DELAY)
        
        # Commit all successful inserts
        session.commit()
        
        print()
        print("=" * 60)
        print("SYNC COMPLETE")
        print("=" * 60)
        print(f"Total listings: {len(listings)}")
        print(f"Successful: {success_count}")
        print(f"Errors: {error_count}")
        print(f"Finished at: {datetime.now(timezone.utc).isoformat()}")
        
    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(sync_market_data())
