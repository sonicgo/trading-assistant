"""
test_data_quality.py — Phase 2 Test Suite

Covers (playbook §6.1):
  - test_dq_gbx_guard_detects_100x_mismatch
  - test_dq_stale_close_creates_alert
  - test_missing_close_only_after_market_close_time

Additional coverage:
  - GBX scale: 100x too large direction
  - Staleness severity escalation
  - Intraday staleness
  - Price jump rule
  - Currency mismatch
  - FX missing / stale
  - Full evaluate_dq integration with mock DB data
"""
import uuid
import zoneinfo
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.domain.models import Portfolio, PricePoint, InstrumentListing
from app.services.data_quality import (
    DQViolation,
    check_gbx_scale,
    check_staleness_close,
    check_staleness_intraday,
    check_missing_close,
    check_price_jump,
    check_currency_mismatch,
    check_fx_missing,
    check_fx_stale,
    _is_market_closed,
)
from app.services.market_data_adapter import FxQuote, PriceQuote


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_listing(
    ticker: str = "LLOY",
    exchange: str = "LSE",
    trading_currency: str = "GBP",
    quote_scale: str = "MINOR",
    listing_id: str | None = None,
) -> MagicMock:
    """Build a lightweight mock InstrumentListing for pure-function tests."""
    m = MagicMock(spec=InstrumentListing)
    m.listing_id = listing_id or str(uuid.uuid4())
    m.ticker = ticker
    m.exchange = exchange
    m.trading_currency = trading_currency
    m.quote_scale = quote_scale
    return m


def _make_price_point(
    price: str,
    as_of: datetime,
    is_close: bool = True,
) -> MagicMock:
    m = MagicMock(spec=PricePoint)
    m.price = Decimal(price)
    m.as_of = as_of
    m.is_close = is_close
    return m


NOW = datetime(2026, 2, 28, 17, 0, 0, tzinfo=timezone.utc)  # after LSE close


# ─── Test 2: DQ_GBX_SCALE 100× mismatch (playbook §6.1) ──────────────────────


def test_dq_gbx_guard_detects_100x_mismatch():
    """
    GBX/GBP scale mismatch (100× too small) is detected as CRITICAL.

    Scenario: listing stores price as GBX pence (previous close = 5000p).
    Provider returns 50.00 GBP (÷100 error) — ratio ≈ 0.01 → CRITICAL.
    """
    listing = _make_listing(trading_currency="GBP", quote_scale="MINOR")

    # Previous close was 5000 GBX pence
    previous_close = Decimal("5000")

    # Provider returns 50.00 (GBP instead of GBX) — 100× too small
    price_quote = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW,
        price="50.00",
        currency="GBP",
        is_close=True,
        raw={"test": True},
    )

    violation = check_gbx_scale(listing, price_quote, previous_close)

    assert violation is not None, "Should detect 100× scale mismatch (too small)"
    assert violation.rule_code == "DQ_GBX_SCALE"
    assert violation.severity == "CRITICAL"
    # Ratio should be ~0.01
    assert 0.005 < violation.details["ratio"] < 0.02, (
        f"Expected ratio ~0.01 but got {violation.details['ratio']}"
    )


def test_dq_gbx_guard_detects_100x_mismatch_db_listing(db: Session, test_portfolio: Portfolio):
    """
    Same mismatch test but using a real InstrumentListing from the DB fixture.
    """
    from app.domain.models import PortfolioConstituent, InstrumentListing

    constituent = (
        db.query(PortfolioConstituent)
        .filter_by(portfolio_id=test_portfolio.portfolio_id)
        .first()
    )
    assert constituent is not None, "Fixture must create a constituent"
    listing = db.get(InstrumentListing, constituent.listing_id)
    assert listing is not None

    previous_close = Decimal("5000")
    price_quote = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW,
        price="50.00",
        currency="GBP",
        is_close=True,
        raw={"test": True},
    )

    violation = check_gbx_scale(listing, price_quote, previous_close)

    assert violation is not None
    assert violation.rule_code == "DQ_GBX_SCALE"
    assert violation.severity == "CRITICAL"
    # Check human-readable message references the currencies
    assert "GBP" in violation.message or "GBX" in violation.message


def test_dq_gbx_guard_detects_100x_too_large():
    """
    Provider returned GBX pence (2800) when listing expects GBP (28).
    Ratio ≈ 100 → CRITICAL.
    """
    listing = _make_listing(
        ticker="SHEL", trading_currency="GBP", quote_scale="MAJOR"
    )
    previous_close = Decimal("28")
    price_quote = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW,
        price="2800",
        currency="GBX",
        is_close=False,
        raw=None,
    )

    violation = check_gbx_scale(listing, price_quote, previous_close)

    assert violation is not None
    assert violation.rule_code == "DQ_GBX_SCALE"
    assert violation.severity == "CRITICAL"
    assert 50 < violation.details["ratio"] < 150


def test_dq_gbx_guard_silent_for_normal_price():
    """Normal price (ratio ≈ 1) should produce no GBX violation."""
    listing = _make_listing(trading_currency="GBX", quote_scale="MINOR")
    previous_close = Decimal("50")
    normal_quote = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW,
        price="51",
        currency="GBX",
        is_close=True,
        raw=None,
    )
    assert check_gbx_scale(listing, normal_quote, previous_close) is None


def test_dq_gbx_guard_silent_when_no_previous_close():
    """No previous close → no baseline → cannot detect scale error."""
    listing = _make_listing()
    quote = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW,
        price="50.00",
        currency="GBP",
        is_close=True,
        raw=None,
    )
    assert check_gbx_scale(listing, quote, None) is None


# ─── Test 3: DQ_STALE_CLOSE (playbook §6.1) ───────────────────────────────────


def test_dq_stale_close_creates_alert(db: Session, test_portfolio: Portfolio):
    """
    A close price older than dq_stale_max_days_close triggers DQ_STALE_CLOSE.

    Creates a real PricePoint in the DB (5 days old) and runs the staleness
    check.  Confirms the returned DQViolation has the correct rule_code.
    """
    from app.domain.models import PortfolioConstituent, InstrumentListing
    from sqlalchemy import text

    constituent = (
        db.query(PortfolioConstituent)
        .filter_by(portfolio_id=test_portfolio.portfolio_id)
        .first()
    )
    listing = db.get(InstrumentListing, constituent.listing_id)

    stale_as_of = NOW - timedelta(days=5)

    stale_price = PricePoint(
        price_point_id=uuid.uuid4(),
        listing_id=listing.listing_id,
        as_of=stale_as_of,
        price=Decimal("100.00"),
        currency="GBP",
        is_close=True,
        source_id="test_stale",
        raw=None,
    )
    db.add(stale_price)
    db.commit()

    violation = check_staleness_close(listing, stale_price, NOW)

    assert violation is not None, "Should detect stale close price"
    assert violation.rule_code == "DQ_STALE_CLOSE"
    # 5 days old with threshold of 3 → WARN (< 6 days = 2× threshold)
    assert violation.severity in ("WARN", "CRITICAL")
    assert "5" in violation.message or "4" in violation.message or "days" in violation.message


def test_dq_stale_close_severity_escalates_to_critical():
    """
    Age > 2× threshold escalates from WARN to CRITICAL.
    Default threshold = 3 days; >6 days → CRITICAL.
    """
    listing = _make_listing()
    very_old_close = _make_price_point("50", NOW - timedelta(days=10))

    violation = check_staleness_close(listing, very_old_close, NOW)

    assert violation is not None
    assert violation.severity == "CRITICAL"


def test_dq_stale_close_silent_for_fresh_price():
    """Fresh close (within threshold) → no violation."""
    listing = _make_listing()
    fresh = _make_price_point("50", NOW - timedelta(hours=6))
    assert check_staleness_close(listing, fresh, NOW) is None


def test_dq_stale_close_silent_when_no_close():
    """None latest_close → DQ_STALE_CLOSE skips (DQ_MISSING handles absence)."""
    listing = _make_listing()
    assert check_staleness_close(listing, None, NOW) is None


# ─── Test 4: DQ_MISSING_CLOSE market-close awareness (playbook §6.1) ──────────


def test_missing_close_only_after_market_close_time():
    """
    DQ_MISSING_CLOSE only fires AFTER market close, never BEFORE.

    LSE closes at 16:30 London time.
    - 09:00 UTC on a weekday (pre-close): no violation
    - 17:00 UTC (post-16:30 BST in winter = 17:00 UTC): violation fired
    """
    london_tz = zoneinfo.ZoneInfo("Europe/London")

    listing = _make_listing(exchange="LSE")

    # ── Before market close: 09:00 UTC = 09:00 London (winter) ───────────────
    before_close = datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc)
    violation_before = check_missing_close(listing, None, before_close)
    assert violation_before is None, (
        "Should NOT flag missing close before market close (09:00 London)"
    )

    # ── After market close: 17:00 UTC = 17:00 London (winter, after 16:30) ───
    after_close = datetime(2026, 2, 28, 17, 0, tzinfo=timezone.utc)
    violation_after = check_missing_close(listing, None, after_close)
    assert violation_after is not None, (
        "Should flag missing close after market close (17:00 London)"
    )
    assert violation_after.rule_code == "DQ_MISSING_CLOSE"
    assert violation_after.severity == "CRITICAL"


def test_missing_close_silent_when_close_exists():
    """No violation when a close price is available, even post-market."""
    listing = _make_listing(exchange="LSE")
    existing_close = _make_price_point("50", NOW - timedelta(hours=2))
    assert check_missing_close(listing, existing_close, NOW) is None


def test_missing_close_unknown_exchange_is_conservative():
    """Unknown exchange defaults to market-closed (conservative)."""
    listing = _make_listing(exchange="UNKNOWN_XYZ")
    violation = check_missing_close(listing, None, NOW)
    # dq_require_close=True (default) + unknown exchange → should fire
    assert violation is not None
    assert violation.rule_code == "DQ_MISSING_CLOSE"


# ─── Additional DQ rule coverage ──────────────────────────────────────────────


def test_dq_stale_intraday_fires_on_old_data():
    """Intraday price older than DQ_STALE_MAX_MINUTES_INTRADAY → WARN."""
    listing = _make_listing()
    old = _make_price_point("50", NOW - timedelta(hours=2), is_close=False)
    violation = check_staleness_intraday(listing, old, NOW)
    assert violation is not None
    assert violation.rule_code == "DQ_STALE_INTRADAY"
    assert violation.severity == "WARN"


def test_dq_stale_intraday_silent_for_fresh():
    listing = _make_listing()
    fresh = _make_price_point("50", NOW - timedelta(minutes=5), is_close=False)
    assert check_staleness_intraday(listing, fresh, NOW) is None


def test_dq_jump_close_fires_for_large_move():
    """12% price move (above 10% default threshold) → DQ_JUMP_CLOSE."""
    listing = _make_listing()
    prev_c = _make_price_point("50", NOW - timedelta(days=1))
    jump_c = _make_price_point("56", NOW)  # 12% move
    violation = check_price_jump(listing, jump_c, prev_c)
    assert violation is not None
    assert violation.rule_code == "DQ_JUMP_CLOSE"
    assert violation.severity == "CRITICAL"


def test_dq_jump_close_silent_at_boundary():
    """Exactly 10% move — strict > means boundary is NOT triggered."""
    listing = _make_listing()
    prev_c = _make_price_point("50", NOW - timedelta(days=1))
    boundary = _make_price_point("55", NOW)   # exactly 10%
    assert check_price_jump(listing, boundary, prev_c) is None


def test_dq_ccy_mismatch_fires_for_wrong_currency():
    listing = _make_listing(trading_currency="GBX")
    usd_q = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW, price="51", currency="USD",
        is_close=False, raw=None,
    )
    violation = check_currency_mismatch(listing, usd_q)
    assert violation is not None
    assert violation.rule_code == "DQ_CCY_MISMATCH"


def test_dq_ccy_mismatch_silent_for_gbp_on_gbx():
    """GBP on a GBX listing is same currency family — no CCY mismatch."""
    listing = _make_listing(trading_currency="GBX")
    gbp_q = PriceQuote(
        listing_id=str(listing.listing_id),
        as_of=NOW, price="0.50", currency="GBP",
        is_close=False, raw=None,
    )
    assert check_currency_mismatch(listing, gbp_q) is None


def test_dq_fx_missing_fires_when_no_fx_available():
    usd_listing = _make_listing(trading_currency="USD")
    violation = check_fx_missing(usd_listing, "GBP", [])
    assert violation is not None
    assert violation.rule_code == "DQ_FX_MISSING"


def test_dq_fx_missing_silent_when_fx_available():
    usd_listing = _make_listing(trading_currency="USD")
    fx_q = FxQuote(base_ccy="GBP", quote_ccy="USD", as_of=NOW, rate="1.27", raw=None)
    assert check_fx_missing(usd_listing, "GBP", [fx_q]) is None


def test_dq_fx_stale_fires_for_old_rate():
    usd_listing = _make_listing(trading_currency="USD")
    stale_fx = FxQuote(
        base_ccy="USD", quote_ccy="GBP",
        as_of=NOW - timedelta(days=5),
        rate="1.27", raw=None,
    )
    violation = check_fx_stale(usd_listing, "GBP", [stale_fx], NOW)
    assert violation is not None
    assert violation.rule_code == "DQ_FX_STALE"
    assert violation.severity == "WARN"


def test_dq_market_closed_lse_is_closed_at_1700_utc():
    """LSE is closed at 17:00 UTC on a weekday (= 17:00 London winter time)."""
    assert _is_market_closed("LSE", NOW) is True


def test_dq_market_closed_lse_is_open_at_0900_utc():
    market_open = datetime(2026, 2, 28, 9, 0, 0, tzinfo=timezone.utc)
    assert _is_market_closed("LSE", market_open) is False
