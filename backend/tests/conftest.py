"""
Test fixtures for Phase 2 test suite.

Uses real Postgres (docker-dev runtime) — no SQLite or in-memory fakes.
Fixtures create and clean up their own data using unique UUIDs.

NOTE: Several services (alerts, freeze) call db.commit() internally.
The fixture teardown therefore uses explicit deletes rather than relying
on a single outer rollback.
"""
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.models import (
    User,
    Portfolio,
    Instrument,
    InstrumentListing,
    PortfolioConstituent,
    Sleeve,
    PricePoint,
    Alert,
    FreezeState,
    TaskRun,
    RunInputSnapshot,
    Notification,
)
from app.services.providers.mock_provider import MockProvider


# ─── Database Session ──────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def db():
    """
    Provide a database session for each test.

    Because several service functions (create_alert, freeze_portfolio) call
    db.commit() internally, we cannot rely on a top-level rollback to clean up.
    Each fixture below performs its own teardown via explicit deletes.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()


# ─── Core Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def test_user(db: Session):
    """Create a unique test user; delete after test."""
    user = User(
        user_id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_password_for_tests",
        is_enabled=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # Teardown — delete dependent rows then the user
    try:
        db.execute(
            text(
                "DELETE FROM notifications WHERE owner_user_id = :uid"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM freeze_states WHERE portfolio_id IN "
                "(SELECT portfolio_id FROM portfolio WHERE owner_user_id = :uid)"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM alerts WHERE portfolio_id IN "
                "(SELECT portfolio_id FROM portfolio WHERE owner_user_id = :uid)"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM run_input_snapshots WHERE run_id IN "
                "(SELECT run_id FROM task_runs WHERE portfolio_id IN "
                "(SELECT portfolio_id FROM portfolio WHERE owner_user_id = :uid))"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM task_runs WHERE portfolio_id IN "
                "(SELECT portfolio_id FROM portfolio WHERE owner_user_id = :uid)"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM price_points WHERE listing_id IN ("
                "  SELECT pc.listing_id FROM portfolio_constituent pc "
                "  JOIN portfolio p ON p.portfolio_id = pc.portfolio_id "
                "  WHERE p.owner_user_id = :uid"
                ")"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text(
                "DELETE FROM portfolio_constituent WHERE portfolio_id IN "
                "(SELECT portfolio_id FROM portfolio WHERE owner_user_id = :uid)"
            ),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text("DELETE FROM portfolio WHERE owner_user_id = :uid"),
            {"uid": str(user.user_id)},
        )
        db.execute(
            text("DELETE FROM \"user\" WHERE user_id = :uid"),
            {"uid": str(user.user_id)},
        )
        db.commit()
    except Exception:
        db.rollback()


@pytest.fixture
def sleeve_core(db: Session):
    """Ensure 'CORE' sleeve exists (idempotent)."""
    existing = db.query(Sleeve).filter_by(sleeve_code="CORE").first()
    if not existing:
        sleeve = Sleeve(sleeve_code="CORE", name="Core Sleeve")
        db.add(sleeve)
        db.commit()
    yield


@pytest.fixture
def test_portfolio(db: Session, test_user: User, sleeve_core):
    """
    Create a complete test portfolio:
      - Portfolio owned by test_user
      - One Instrument + InstrumentListing (LSE/GBP)
      - One monitored PortfolioConstituent

    Teardown is handled by the test_user fixture (cascade delete by owner_user_id).
    Instrument + listing are cleaned up separately because they're not
    owned by the user.
    """
    instrument_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()

    instrument = Instrument(
        instrument_id=instrument_id,
        isin=f"GB{uuid.uuid4().hex[:10].upper()}",
        instrument_type="ETF",
        name="Test ETF",
    )
    db.add(instrument)
    db.commit()

    listing = InstrumentListing(
        listing_id=listing_id,
        instrument_id=instrument_id,
        ticker=f"TST{uuid.uuid4().hex[:4].upper()}",
        exchange="LSE",
        trading_currency="GBP",
        quote_scale="MINOR",   # GBX (pence) scale for LSE
        is_primary=True,
    )
    db.add(listing)
    db.commit()

    portfolio = Portfolio(
        portfolio_id=portfolio_id,
        owner_user_id=test_user.user_id,
        name="Test Portfolio",
        broker="Test Broker",
        base_currency="GBP",
        tax_profile="ISA",
        is_enabled=True,
    )
    db.add(portfolio)
    db.commit()

    constituent = PortfolioConstituent(
        portfolio_id=portfolio_id,
        listing_id=listing_id,
        sleeve_code="CORE",
        is_monitored=True,
    )
    db.add(constituent)
    db.commit()

    db.refresh(portfolio)
    db.refresh(listing)

    # Attach listing reference for convenience in tests
    portfolio._test_listing = listing

    yield portfolio

    # Extra cleanup: instrument + listing (user fixture cleans portfolio/constituent)
    try:
        db.execute(
            text("DELETE FROM price_points WHERE listing_id = :lid"),
            {"lid": str(listing_id)},
        )
        db.execute(
            text("DELETE FROM portfolio_constituent WHERE listing_id = :lid"),
            {"lid": str(listing_id)},
        )
        db.execute(
            text("DELETE FROM listing WHERE listing_id = :lid"),
            {"lid": str(listing_id)},
        )
        db.execute(
            text("DELETE FROM instrument WHERE instrument_id = :iid"),
            {"iid": str(instrument_id)},
        )
        db.commit()
    except Exception:
        db.rollback()


# ─── Mock Provider Variants ───────────────────────────────────────────────────


@pytest.fixture
def mock_adapter():
    """Return a standard MockProvider (no anomalies)."""
    return MockProvider()


@pytest.fixture
def mock_adapter_scale_mismatch():
    """Return MockProvider configured to produce scale mismatch (100×)."""
    return MockProvider(scale_mismatch=True)


@pytest.fixture
def mock_adapter_stale():
    """Return MockProvider configured to produce stale prices."""
    return MockProvider(stale_prices=True)
