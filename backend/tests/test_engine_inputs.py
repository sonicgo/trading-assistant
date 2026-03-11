import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.domain.models import (
    CashSnapshot,
    FreezeState,
    HoldingSnapshot,
    Portfolio,
    PortfolioPolicyAllocation,
    PricePoint,
)
from app.services.engine_inputs import EngineInputResult, gather_engine_inputs


NOW = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)


def _seed_cash_holding_and_allocation(
    db: Session,
    test_portfolio: Portfolio,
    *,
    ticker: str = "TST1",
    policy_hash: str | None = None,
) -> None:
    _ensure_policy_allocations_table(db)
    listing = test_portfolio._test_listing

    cash_snapshot = CashSnapshot(
        portfolio_id=test_portfolio.portfolio_id,
        balance_gbp=Decimal("250.00"),
        updated_at=NOW,
        version_no=1,
    )
    holding_snapshot = HoldingSnapshot(
        portfolio_id=test_portfolio.portfolio_id,
        listing_id=listing.listing_id,
        quantity=Decimal("10.0000000000"),
        book_cost_gbp=Decimal("1000.0000000000"),
        avg_cost_gbp=Decimal("100.0000000000"),
        updated_at=NOW,
        version_no=1,
    )
    allocation = PortfolioPolicyAllocation(
        portfolio_policy_allocation_id=uuid.uuid4(),
        portfolio_id=test_portfolio.portfolio_id,
        listing_id=listing.listing_id,
        ticker=ticker,
        sleeve_code="CORE",
        policy_role="STRATEGIC",
        target_weight_pct=Decimal("35.00000000"),
        priority_rank=1,
        policy_hash=policy_hash or f"policy-{uuid.uuid4().hex[:8]}",
    )

    db.add(cash_snapshot)
    db.add(holding_snapshot)
    db.add(allocation)
    db.commit()


def _ensure_policy_allocations_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS portfolio_policy_allocations (
                portfolio_policy_allocation_id UUID PRIMARY KEY,
                portfolio_id UUID NOT NULL REFERENCES portfolio(portfolio_id),
                listing_id UUID NOT NULL REFERENCES listing(listing_id),
                ticker VARCHAR NOT NULL,
                sleeve_code VARCHAR NOT NULL,
                policy_role VARCHAR NOT NULL,
                target_weight_pct NUMERIC(18, 8),
                priority_rank INTEGER,
                policy_hash VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_allocation
            ON portfolio_policy_allocations (portfolio_id, policy_hash, listing_id)
            """
        )
    )
    db.commit()


@pytest.mark.asyncio
async def test_run_blocked_when_required_price_is_older_than_3_days(
    db: Session,
    test_portfolio: Portfolio,
):
    listing = test_portfolio._test_listing
    _seed_cash_holding_and_allocation(db, test_portfolio, ticker=listing.ticker)

    stale_price = PricePoint(
        price_point_id=uuid.uuid4(),
        listing_id=listing.listing_id,
        as_of=NOW - timedelta(days=4),
        price=Decimal("101.25"),
        currency="GBP",
        is_close=True,
        source_id="test_engine_inputs_stale",
        raw=None,
    )
    db.add(stale_price)
    db.commit()

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert isinstance(result, EngineInputResult)
    assert result.is_blocked is True
    assert result.block_reason == "STALE_PRICE"
    assert result.block_message is not None
    assert "older than 3 days" in result.block_message


@pytest.mark.asyncio
async def test_run_succeeds_with_fresh_prices(
    db: Session,
    test_portfolio: Portfolio,
):
    listing = test_portfolio._test_listing
    _seed_cash_holding_and_allocation(db, test_portfolio, ticker=listing.ticker)

    fresh_price = PricePoint(
        price_point_id=uuid.uuid4(),
        listing_id=listing.listing_id,
        as_of=NOW - timedelta(days=1),
        price=Decimal("102.50"),
        currency="GBP",
        is_close=True,
        source_id="test_engine_inputs_fresh",
        raw=None,
    )
    db.add(fresh_price)
    db.commit()

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert result.is_blocked is False
    assert result.block_reason is None
    assert result.snapshot_data is not None
    assert "cash_snapshot" in result.snapshot_data
    assert "holding_snapshots" in result.snapshot_data
    assert "price_points_used" in result.snapshot_data
    assert "allocation_map" in result.snapshot_data


@pytest.mark.asyncio
async def test_run_blocked_when_portfolio_frozen(
    db: Session,
    test_portfolio: Portfolio,
):
    freeze_state = FreezeState(
        freeze_id=uuid.uuid4(),
        portfolio_id=test_portfolio.portfolio_id,
        is_frozen=True,
    )
    db.add(freeze_state)
    db.commit()

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert result.is_blocked is True
    assert result.block_reason == "FROZEN"
    assert result.block_message is not None


@pytest.mark.asyncio
async def test_run_blocked_when_price_missing(
    db: Session,
    test_portfolio: Portfolio,
):
    _seed_cash_holding_and_allocation(db, test_portfolio, ticker=test_portfolio._test_listing.ticker)

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert result.is_blocked is True
    assert result.block_reason == "MISSING_PRICE"
    assert result.block_message is not None


@pytest.mark.asyncio
async def test_snapshot_contains_cash_and_holdings(
    db: Session,
    test_portfolio: Portfolio,
):
    listing = test_portfolio._test_listing
    _seed_cash_holding_and_allocation(db, test_portfolio, ticker=listing.ticker)

    fresh_price = PricePoint(
        price_point_id=uuid.uuid4(),
        listing_id=listing.listing_id,
        as_of=NOW - timedelta(days=1),
        price=Decimal("103.00"),
        currency="GBP",
        is_close=True,
        source_id="test_engine_inputs_snapshot",
        raw=None,
    )
    db.add(fresh_price)
    db.commit()

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert result.is_blocked is False
    assert result.snapshot_data is not None
    assert "cash_snapshot" in result.snapshot_data
    assert "holding_snapshots" in result.snapshot_data

    cash_snapshot = result.snapshot_data["cash_snapshot"]
    holdings = result.snapshot_data["holding_snapshots"]

    assert cash_snapshot["balance_gbp"] == "250.0000000000"
    assert len(holdings) == 1
    assert holdings[0]["listing_id"] == str(listing.listing_id)
    assert holdings[0]["quantity"] == "10.0000000000"


@pytest.mark.asyncio
async def test_snapshot_contains_allocation_map(
    db: Session,
    test_portfolio: Portfolio,
):
    listing = test_portfolio._test_listing
    _seed_cash_holding_and_allocation(db, test_portfolio, ticker=listing.ticker)

    fresh_price = PricePoint(
        price_point_id=uuid.uuid4(),
        listing_id=listing.listing_id,
        as_of=NOW - timedelta(days=1),
        price=Decimal("99.95"),
        currency="GBP",
        is_close=True,
        source_id="test_engine_inputs_allocation",
        raw=None,
    )
    db.add(fresh_price)
    db.commit()

    result = gather_engine_inputs(db, str(test_portfolio.portfolio_id), NOW)

    assert result.is_blocked is False
    assert result.snapshot_data is not None
    assert "allocation_map" in result.snapshot_data

    allocation_map = result.snapshot_data["allocation_map"]
    assert len(allocation_map) == 1
    assert allocation_map[0]["listing_id"] == str(listing.listing_id)
    assert allocation_map[0]["ticker"] == listing.ticker
    assert allocation_map[0]["sleeve_code"] == "CORE"
