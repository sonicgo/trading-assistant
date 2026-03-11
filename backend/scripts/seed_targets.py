#!/usr/bin/env python3
"""Seed portfolio policy allocations from manifesto."""
import os
import sys
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import Portfolio, InstrumentListing, PortfolioPolicyAllocation

# Target allocations from manifesto policy
TARGETS = [
    {"ticker": "VWRP", "sleeve_code": "core", "role": "INVESTED_ASSET", "weight": Decimal("35.0"), "rank": 1},
    {"ticker": "SEMI", "sleeve_code": "semis", "role": "INVESTED_ASSET", "weight": Decimal("35.0"), "rank": 2},
    {"ticker": "XWES", "sleeve_code": "energy", "role": "INVESTED_ASSET", "weight": Decimal("10.0"), "rank": 3},
    {"ticker": "XWHS", "sleeve_code": "healthcare", "role": "INVESTED_ASSET", "weight": Decimal("10.0"), "rank": 4},
    {"ticker": "WLDS", "sleeve_code": "small_cap", "role": "INVESTED_ASSET", "weight": Decimal("5.0"), "rank": 5},
    {"ticker": "IGL5", "sleeve_code": "short_gilts", "role": "INVESTED_ASSET", "weight": Decimal("5.0"), "rank": 6},
    {"ticker": "CSH2", "sleeve_code": "cash_park", "role": "CASH_PARK", "weight": None, "rank": 7},
]

POLICY_HASH = "manifesto_v1.0.0"


def get_or_create_session():
    """Create SQLAlchemy session from DATABASE_URL env var."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def get_test_portfolio(session):
    """Query for the default test portfolio (SIPP)."""
    portfolio = session.query(Portfolio).filter(Portfolio.name == "SIPP").first()
    if not portfolio:
        # Try to get any enabled portfolio
        portfolio = session.query(Portfolio).filter(Portfolio.is_enabled == True).first()
    if not portfolio:
        raise ValueError("No enabled portfolio found. Please create a portfolio first.")
    return portfolio


def get_listings_by_tickers(session, tickers):
    """Query listings by ticker symbols."""
    listings = session.query(InstrumentListing).filter(
        InstrumentListing.ticker.in_(tickers)
    ).all()

    if len(listings) != len(tickers):
        found_tickers = {lst.ticker for lst in listings}
        missing = set(tickers) - found_tickers
        raise ValueError(f"Missing listings for tickers: {missing}")

    # Return as dict for easy lookup
    return {lst.ticker: lst for lst in listings}


def seed_allocations(session, portfolio, listings):
    """Create or update portfolio policy allocations."""
    # Check if allocations already exist for this policy hash
    existing = session.query(PortfolioPolicyAllocation).filter(
        PortfolioPolicyAllocation.portfolio_id == portfolio.portfolio_id,
        PortfolioPolicyAllocation.policy_hash == POLICY_HASH
    ).first()

    if existing:
        print(f"Allocations already exist for policy_hash={POLICY_HASH}. Skipping (idempotent).")
        return []

    created = []
    for target in TARGETS:
        ticker = target["ticker"]
        listing = listings[ticker]

        allocation = PortfolioPolicyAllocation(
            portfolio_id=portfolio.portfolio_id,
            listing_id=listing.listing_id,
            ticker=ticker,
            sleeve_code=target["sleeve_code"],
            policy_role=target["role"],
            target_weight_pct=target["weight"],
            priority_rank=target["rank"],
            policy_hash=POLICY_HASH,
        )
        session.add(allocation)
        created.append(target)

    session.commit()
    return created


def main():
    """Main entry point."""
    print(f"Database URL: {os.getenv('DATABASE_URL', 'NOT SET')[:30]}...")

    session = get_or_create_session()

    try:
        # Get test portfolio
        portfolio = get_test_portfolio(session)
        print(f"Using portfolio: {portfolio.name} ({portfolio.portfolio_id})")

        # Get listings by ticker
        tickers = [t["ticker"] for t in TARGETS]
        listings = get_listings_by_tickers(session, tickers)
        print(f"Found {len(listings)} listings: {list(listings.keys())}")

        # Seed allocations
        created = seed_allocations(session, portfolio, listings)

        if created:
            print(f"\nSeeded {len(created)} policy allocations:")
            for target in created:
                weight_str = f"{target['weight']}%" if target['weight'] else "NULL"
                print(f"  - {target['ticker']}: sleeve={target['sleeve_code']}, "
                      f"role={target['role']}, weight={weight_str}, rank={target['rank']}")
        else:
            print("\nNo new allocations created (already exist).")

        print(f"\nDone. Policy hash: {POLICY_HASH}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
