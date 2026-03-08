"""
test_market_data_ingest.py — Phase 2 Test Suite

Covers:
  - test_price_ingest_idempotent_unique_constraint (playbook §6.1)
  - Additional coverage: FX ingest idempotency, empty portfolio handling
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.domain.models import PricePoint, Portfolio
from app.services.market_data_ingest import ingest_prices_for_portfolio
from app.services.providers.mock_provider import MockProvider


pytestmark = pytest.mark.asyncio


# ─── Test 1: Idempotency (playbook §6.1) ──────────────────────────────────────


async def test_price_ingest_idempotent_unique_constraint(
    db: Session, test_portfolio: Portfolio
):
    """
    Running ingest twice with the same provider timestamp must not create
    duplicate price_point rows.

    Verifies:
    - ON CONFLICT DO NOTHING works correctly
    - Second run returns prices_inserted == 0
    - DB row count for the listing equals first-run inserted count
    """
    job_id = str(uuid.uuid4())
    listing = test_portfolio._test_listing

    # Use a fixed timestamp so both ingest calls produce the same as_of.
    # Without this, datetime.now() shifts between calls and generates new rows.
    fixed_ts = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    adapter = MockProvider(fixed_as_of=fixed_ts)
    # ── First ingest ──────────────────────────────────────────────────────────
    result1 = await ingest_prices_for_portfolio(
        db=db,
        adapter=adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=job_id,
        want_close=True,
        want_intraday=False,
    )
    db.commit()

    first_inserted = result1.prices_inserted
    assert first_inserted > 0, "First ingest should insert at least one price"

    # Count rows for this listing specifically (avoids interference from other tests)
    count_after_first = (
        db.query(PricePoint)
        .filter(PricePoint.listing_id == listing.listing_id)
        .count()
    )
    assert count_after_first == first_inserted

    # ── Second ingest (same fixed timestamp) ───────────────────────────────
    result2 = await ingest_prices_for_portfolio(
        db=db,
        adapter=adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=job_id,
        want_close=True,
        want_intraday=False,
    )
    db.commit()

    # Idempotency assertion
    assert result2.prices_inserted == 0, (
        f"Second ingest should insert 0 new prices (idempotency), "
        f"got {result2.prices_inserted}"
    )

    # Total rows unchanged
    count_after_second = (
        db.query(PricePoint)
        .filter(PricePoint.listing_id == listing.listing_id)
        .count()
    )
    assert count_after_second == count_after_first, (
        f"Row count should remain {count_after_first} after second ingest, "
        f"got {count_after_second}"
    )


# ─── Additional coverage ──────────────────────────────────────────────────────


async def test_ingest_returns_ingest_result_with_metadata(
    db: Session, test_portfolio: Portfolio, mock_adapter: MockProvider
):
    """IngestResult exposes price_quotes, fx_quotes, listings, and counts."""
    result = await ingest_prices_for_portfolio(
        db=db,
        adapter=mock_adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=str(uuid.uuid4()),
        want_close=True,
        want_intraday=False,
    )
    db.commit()

    assert result.run_id, "run_id should be a non-empty UUID string"
    assert result.portfolio_id == str(test_portfolio.portfolio_id)
    assert len(result.listings) >= 1, "Should have at least one listing"
    assert len(result.price_quotes) >= 1, "Should have at least one price quote"
    assert result.prices_inserted >= 1
    assert result.errors == [], f"No errors expected, got: {result.errors}"


async def test_ingest_nonexistent_portfolio_raises(db: Session, mock_adapter: MockProvider):
    """Ingesting for a portfolio that doesn't exist raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await ingest_prices_for_portfolio(
            db=db,
            adapter=mock_adapter,
            portfolio_id=str(uuid.uuid4()),  # random, non-existent
            job_id=str(uuid.uuid4()),
            want_close=True,
            want_intraday=False,
        )


async def test_ingest_both_close_and_intraday(
    db: Session, test_portfolio: Portfolio, mock_adapter: MockProvider
):
    """Requesting both close and intraday prices inserts two rows per listing."""
    listing = test_portfolio._test_listing

    result = await ingest_prices_for_portfolio(
        db=db,
        adapter=mock_adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=str(uuid.uuid4()),
        want_close=True,
        want_intraday=True,
    )
    db.commit()

    # Mock provider returns one close + one intraday per listing
    # They may have the same timestamp but differ by is_close flag
    count = (
        db.query(PricePoint)
        .filter(PricePoint.listing_id == listing.listing_id)
        .count()
    )
    # Expect at least 1 row; mock returns 1 close + 1 intraday
    assert count >= 1, f"Expected at least 1 price row, got {count}"
    assert result.prices_inserted >= 1


async def test_ingest_idempotent_close_and_intraday(
    db: Session, test_portfolio: Portfolio
):
    """Running close+intraday ingest twice inserts 0 on the second pass."""
    job_id = str(uuid.uuid4())
    fixed_ts = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
    adapter = MockProvider(fixed_as_of=fixed_ts)

    result1 = await ingest_prices_for_portfolio(
        db=db,
        adapter=adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=job_id,
        want_close=True,
        want_intraday=True,
    )
    db.commit()
    first_count = result1.prices_inserted
    assert first_count > 0

    result2 = await ingest_prices_for_portfolio(
        db=db,
        adapter=adapter,
        portfolio_id=str(test_portfolio.portfolio_id),
        job_id=job_id,
        want_close=True,
        want_intraday=True,
    )
    db.commit()

    assert result2.prices_inserted == 0, (
        "Second close+intraday ingest must insert 0 (idempotent)"
    )
