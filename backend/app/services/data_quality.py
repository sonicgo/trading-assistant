"""
Data Quality (DQ) Gate — Pure Evaluator
Phase 2: Market Data + Data Quality Gate

Returns DQViolation dataclasses.  Does NOT write to the database.
The caller (worker / ingest pipeline) is responsible for persisting violations
as Alert rows via the alerts service.

Eight rules are enforced:
  DQ_STALE_INTRADAY  – intraday price older than threshold (WARN)
  DQ_STALE_CLOSE     – close price older than threshold   (WARN / CRITICAL)
  DQ_MISSING_CLOSE   – no close after market close        (CRITICAL)
  DQ_JUMP_CLOSE      – abnormal price move vs prev close  (CRITICAL)
  DQ_GBX_SCALE       – 100× GBX/GBP scale hazard         (CRITICAL)
  DQ_CCY_MISMATCH    – provider ccy ≠ listing ccy         (CRITICAL)
  DQ_FX_MISSING      – FX rate needed but absent          (WARN / CRITICAL)
  DQ_FX_STALE        – FX rate older than threshold       (WARN)
"""
from __future__ import annotations

import zoneinfo
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta, time
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import (
    InstrumentListing,
    Portfolio,
    PortfolioConstituent,
    PricePoint,
)
from app.services.market_data_adapter import FxQuote, PriceQuote


# ─── DQ Violation ─────────────────────────────────────────────────────────────


@dataclass
class DQViolation:
    """A single data-quality rule failure.

    Pure data — does NOT interact with the database.
    Callers persist violations as Alert rows using the alerts service.
    """

    rule_code: str
    severity: str  # INFO | WARN | CRITICAL
    listing_id: Optional[str]
    title: str
    message: str
    details: dict = field(default_factory=dict)


# ─── Venue / Market-Close Helpers ─────────────────────────────────────────────

# Exchange codes (as stored in InstrumentListing.exchange) mapped to
# (timezone_name, close_time_HH:MM) tuples sourced from settings.
_VENUE_MAP: dict[str, tuple[str, str]] = {
    # London Stock Exchange
    "LSE":    (settings.venue_lse_tz,  settings.venue_lse_close_time),
    "XLON":   (settings.venue_lse_tz,  settings.venue_lse_close_time),
    "LON":    (settings.venue_lse_tz,  settings.venue_lse_close_time),
    # New York Stock Exchange
    "NYSE":   (settings.venue_nyse_tz, settings.venue_nyse_close_time),
    "XNYS":   (settings.venue_nyse_tz, settings.venue_nyse_close_time),
    # NASDAQ
    "NASDAQ": (settings.venue_nyse_tz, settings.venue_nyse_close_time),
    "XNAS":   (settings.venue_nyse_tz, settings.venue_nyse_close_time),
}


def _is_market_closed(exchange: str, as_of: datetime) -> bool:
    """Return True when the venue was closed at *as_of* (UTC-aware).

    Falls back to True (conservative: market closed) when the venue is not
    recognised, so DQ_MISSING_CLOSE always fires for unknown venues.
    """
    config = _VENUE_MAP.get(exchange.upper())
    if config is None:
        return True  # unknown venue → conservative

    tz_name, close_str = config
    try:
        venue_tz = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, KeyError):
        return True

    venue_now = as_of.astimezone(venue_tz)
    h, m = (int(x) for x in close_str.split(":"))
    return venue_now.time() >= time(h, m)


def _as_utc(dt: datetime) -> datetime:
    """Ensure *dt* is UTC-aware; treat naive datetimes as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ─── Individual Rule Functions ────────────────────────────────────────────────


def check_staleness_intraday(
    listing: InstrumentListing,
    latest_intraday: Optional[PricePoint],
    as_of: datetime,
) -> Optional[DQViolation]:
    """DQ_STALE_INTRADAY: latest intraday price older than threshold (WARN).

    Skipped when no intraday price exists (DQ_MISSING_CLOSE covers that case
    for close prices; absence of intraday is a normal condition outside market
    hours).
    """
    if latest_intraday is None:
        return None

    threshold_minutes = settings.dq_stale_max_minutes_intraday
    age: timedelta = _as_utc(as_of) - _as_utc(latest_intraday.as_of)
    age_minutes = age.total_seconds() / 60

    if age_minutes <= threshold_minutes:
        return None

    return DQViolation(
        rule_code="DQ_STALE_INTRADAY",
        severity="WARN",
        listing_id=str(listing.listing_id),
        title=f"Stale Intraday Price: {listing.ticker}",
        message=(
            f"Latest intraday price is {age_minutes:.1f} min old "
            f"(threshold: {threshold_minutes} min)."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "latest_intraday_as_of": _as_utc(latest_intraday.as_of).isoformat(),
            "as_of": _as_utc(as_of).isoformat(),
            "age_minutes": round(age_minutes, 2),
            "threshold_minutes": threshold_minutes,
        },
    )


def check_staleness_close(
    listing: InstrumentListing,
    latest_close: Optional[PricePoint],
    as_of: datetime,
) -> Optional[DQViolation]:
    """DQ_STALE_CLOSE: latest close price older than threshold.

    Severity escalates to CRITICAL when age exceeds 2× the configured
    threshold (e.g., > 6 days when threshold is 3 days).
    """
    if latest_close is None:
        return None  # absence handled by DQ_MISSING_CLOSE

    threshold_days = settings.dq_stale_max_days_close
    age: timedelta = _as_utc(as_of) - _as_utc(latest_close.as_of)
    age_days = age.total_seconds() / 86_400

    if age_days <= threshold_days:
        return None

    severity = "CRITICAL" if age_days > threshold_days * 2 else "WARN"

    return DQViolation(
        rule_code="DQ_STALE_CLOSE",
        severity=severity,
        listing_id=str(listing.listing_id),
        title=f"Stale Close Price: {listing.ticker}",
        message=(
            f"Latest close price is {age_days:.1f} days old "
            f"(threshold: {threshold_days} days)."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "latest_close_as_of": _as_utc(latest_close.as_of).isoformat(),
            "as_of": _as_utc(as_of).isoformat(),
            "age_days": round(age_days, 2),
            "threshold_days": threshold_days,
        },
    )


def check_missing_close(
    listing: InstrumentListing,
    latest_close: Optional[PricePoint],
    as_of: datetime,
) -> Optional[DQViolation]:
    """DQ_MISSING_CLOSE: no close price exists AND market is closed (CRITICAL).

    Only fires when:
    - settings.dq_require_close is True, AND
    - latest_close is None, AND
    - the venue's market has already closed for the day.
    """
    if not settings.dq_require_close:
        return None
    if latest_close is not None:
        return None
    if not _is_market_closed(listing.exchange, as_of):
        return None  # market still open — close not yet expected

    return DQViolation(
        rule_code="DQ_MISSING_CLOSE",
        severity="CRITICAL",
        listing_id=str(listing.listing_id),
        title=f"Missing Close Price: {listing.ticker}",
        message=(
            f"No close price found for {listing.ticker} "
            f"(exchange: {listing.exchange}) and the market is currently closed."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "exchange": listing.exchange,
            "as_of": _as_utc(as_of).isoformat(),
        },
    )


def check_price_jump(
    listing: InstrumentListing,
    latest_close: Optional[PricePoint],
    prev_close: Optional[PricePoint],
) -> Optional[DQViolation]:
    """DQ_JUMP_CLOSE: move > configured threshold vs previous close (CRITICAL).

    Requires both a latest and previous close price to compare.
    """
    if latest_close is None or prev_close is None:
        return None

    try:
        current = Decimal(str(latest_close.price))
        previous = Decimal(str(prev_close.price))
    except InvalidOperation:
        return None

    if previous == 0:
        return None

    pct_change = abs(current - previous) / previous * 100
    threshold_pct = Decimal(str(settings.dq_jump_threshold_pct))

    if pct_change <= threshold_pct:
        return None

    return DQViolation(
        rule_code="DQ_JUMP_CLOSE",
        severity="CRITICAL",
        listing_id=str(listing.listing_id),
        title=f"Price Jump Detected: {listing.ticker}",
        message=(
            f"Price moved {float(pct_change):.2f}% vs previous close "
            f"(threshold: {settings.dq_jump_threshold_pct}%)."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "latest_close": str(current),
            "previous_close": str(previous),
            "pct_change": float(pct_change),
            "threshold_pct": settings.dq_jump_threshold_pct,
            "latest_close_as_of": _as_utc(latest_close.as_of).isoformat(),
            "prev_close_as_of": _as_utc(prev_close.as_of).isoformat(),
        },
    )


def check_gbx_scale(
    listing: InstrumentListing,
    price_quote: PriceQuote,
    previous_close: Optional[Decimal],
) -> Optional[DQViolation]:
    """DQ_GBX_SCALE: detect GBX/GBP 100× scale error (CRITICAL).

    GBX (pence) = 100 × GBP.  A provider that returns prices in GBP for a
    GBX-quoted instrument (or vice versa) introduces a 100× valuation hazard.

    Detection relies on the ratio between the incoming price and the most
    recent close stored in the DB:
      - Ratio ≈ 0.01 (range 0.005–0.02): provider price is ~100× too small
        → provider gave GBP, but listing expects GBX (pence).
      - Ratio ≈ 100  (range 50–150):    provider price is ~100× too large
        → provider gave GBX (pence), but listing expects GBP.

    Skipped when no previous close is available (no baseline to compare).
    """
    if previous_close is None or previous_close == 0:
        return None  # no baseline → cannot detect

    try:
        current_price = Decimal(price_quote.price)
    except InvalidOperation:
        return None

    if current_price <= 0:
        return None

    ratio = current_price / previous_close

    # ── Case 1: price ~100× too small (provider GBP, listing expects GBX) ────
    if Decimal("0.005") < ratio < Decimal("0.02"):
        return DQViolation(
            rule_code="DQ_GBX_SCALE",
            severity="CRITICAL",
            listing_id=str(listing.listing_id),
            title=f"GBX/GBP Scale Mismatch (100× too small): {listing.ticker}",
            message=(
                f"Provider price {current_price} appears to be in GBP but listing "
                f"'{listing.ticker}' expects GBX (pence).  "
                f"Ratio vs previous close ({previous_close}): {float(ratio):.4f}."
            ),
            details={
                "listing_id": str(listing.listing_id),
                "ticker": listing.ticker,
                "listing_quote_scale": listing.quote_scale,
                "listing_trading_currency": listing.trading_currency,
                "provider_price": str(current_price),
                "previous_close": str(previous_close),
                "ratio": float(ratio),
                "expected_ratio_range": "0.95–1.05",
                "hazard": "Provider returned GBP; listing expects GBX (pence)",
            },
        )

    # ── Case 2: price ~100× too large (provider GBX, listing expects GBP) ───
    if Decimal("50") < ratio < Decimal("150"):
        return DQViolation(
            rule_code="DQ_GBX_SCALE",
            severity="CRITICAL",
            listing_id=str(listing.listing_id),
            title=f"GBX/GBP Scale Mismatch (100× too large): {listing.ticker}",
            message=(
                f"Provider price {current_price} appears to be in GBX (pence) but "
                f"listing '{listing.ticker}' expects GBP.  "
                f"Ratio vs previous close ({previous_close}): {float(ratio):.4f}."
            ),
            details={
                "listing_id": str(listing.listing_id),
                "ticker": listing.ticker,
                "listing_quote_scale": listing.quote_scale,
                "listing_trading_currency": listing.trading_currency,
                "provider_price": str(current_price),
                "previous_close": str(previous_close),
                "ratio": float(ratio),
                "expected_ratio_range": "0.95–1.05",
                "hazard": "Provider returned GBX (pence); listing expects GBP",
            },
        )

    return None


def check_currency_mismatch(
    listing: InstrumentListing,
    price_quote: PriceQuote,
) -> Optional[DQViolation]:
    """DQ_CCY_MISMATCH: provider currency ≠ listing trading currency (CRITICAL).

    GBX / GBP are treated as the same economic currency family (same instrument
    denominated differently — pence vs pounds).  Scale differences between GBX
    and GBP are handled by DQ_GBX_SCALE rather than here.
    """
    if price_quote.currency is None:
        return None  # provider did not report currency — cannot check

    provider_ccy = price_quote.currency.upper().strip()
    listing_ccy = listing.trading_currency.upper().strip()

    # GBX (pence) and GBP are both valid for the same UK instrument.
    # Scale mismatch is handled by DQ_GBX_SCALE; skip here to avoid duplicate.
    _gbx_family = {"GBX", "GBP"}
    if listing_ccy in _gbx_family and provider_ccy in _gbx_family:
        return None

    if provider_ccy == listing_ccy:
        return None

    return DQViolation(
        rule_code="DQ_CCY_MISMATCH",
        severity="CRITICAL",
        listing_id=str(listing.listing_id),
        title=f"Currency Mismatch: {listing.ticker}",
        message=(
            f"Provider reported currency '{price_quote.currency}' but listing "
            f"'{listing.ticker}' trades in '{listing.trading_currency}'."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "listing_trading_currency": listing.trading_currency,
            "provider_currency": price_quote.currency,
        },
    )


def check_fx_missing(
    listing: InstrumentListing,
    portfolio_base_currency: str,
    fx_quotes: list[FxQuote],
) -> Optional[DQViolation]:
    """DQ_FX_MISSING: FX rate required but not available.

    Severity: CRITICAL when dq_require_close is True, WARN otherwise.
    GBX listings are normalised to GBP for FX lookup (no GBX/GBP FX pair
    exists on markets — they are the same currency at a 100× scale).
    """
    listing_ccy = listing.trading_currency.upper().strip()
    base_ccy = portfolio_base_currency.upper().strip()

    # GBX → GBP normalisation for FX purposes
    if listing_ccy == "GBX":
        listing_ccy = "GBP"

    if listing_ccy == base_ccy:
        return None  # same currency — no FX conversion needed

    pair_found = any(
        (q.base_ccy.upper() == listing_ccy and q.quote_ccy.upper() == base_ccy)
        or (q.base_ccy.upper() == base_ccy and q.quote_ccy.upper() == listing_ccy)
        for q in fx_quotes
    )
    if pair_found:
        return None

    severity = "CRITICAL" if settings.dq_require_close else "WARN"

    return DQViolation(
        rule_code="DQ_FX_MISSING",
        severity=severity,
        listing_id=str(listing.listing_id),
        title=f"FX Rate Missing: {listing_ccy}/{base_ccy}",
        message=(
            f"No FX rate found for {listing_ccy}/{base_ccy} required to value "
            f"'{listing.ticker}' in portfolio base currency {base_ccy}."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "listing_currency": listing_ccy,
            "portfolio_base_currency": base_ccy,
            "available_pairs": [f"{q.base_ccy}/{q.quote_ccy}" for q in fx_quotes],
        },
    )


def check_fx_stale(
    listing: InstrumentListing,
    portfolio_base_currency: str,
    fx_quotes: list[FxQuote],
    as_of: datetime,
) -> Optional[DQViolation]:
    """DQ_FX_STALE: FX rate older than dq_fx_stale_max_days (WARN).

    Evaluates only when a matching FX pair exists (absence is DQ_FX_MISSING).
    """
    listing_ccy = listing.trading_currency.upper().strip()
    base_ccy = portfolio_base_currency.upper().strip()

    # GBX → GBP normalisation for FX purposes
    if listing_ccy == "GBX":
        listing_ccy = "GBP"

    if listing_ccy == base_ccy:
        return None

    matching = [
        q
        for q in fx_quotes
        if (q.base_ccy.upper() == listing_ccy and q.quote_ccy.upper() == base_ccy)
        or (q.base_ccy.upper() == base_ccy and q.quote_ccy.upper() == listing_ccy)
    ]
    if not matching:
        return None  # absence handled by DQ_FX_MISSING

    threshold_days = settings.dq_fx_stale_max_days
    latest_fx = max(matching, key=lambda q: q.as_of)
    age: timedelta = _as_utc(as_of) - _as_utc(latest_fx.as_of)
    age_days = age.total_seconds() / 86_400

    if age_days <= threshold_days:
        return None

    return DQViolation(
        rule_code="DQ_FX_STALE",
        severity="WARN",
        listing_id=str(listing.listing_id),
        title=f"Stale FX Rate: {listing_ccy}/{base_ccy}",
        message=(
            f"FX rate for {listing_ccy}/{base_ccy} is {age_days:.1f} days old "
            f"(threshold: {threshold_days} days)."
        ),
        details={
            "listing_id": str(listing.listing_id),
            "ticker": listing.ticker,
            "listing_currency": listing_ccy,
            "portfolio_base_currency": base_ccy,
            "fx_as_of": _as_utc(latest_fx.as_of).isoformat(),
            "as_of": _as_utc(as_of).isoformat(),
            "age_days": round(age_days, 2),
            "threshold_days": threshold_days,
        },
    )


# ─── Main Evaluator ───────────────────────────────────────────────────────────


def evaluate_dq(
    db: Session,
    portfolio_id: str,
    price_quotes: list[PriceQuote],
    fx_quotes: list[FxQuote],
    as_of: datetime,
) -> list[DQViolation]:
    """Evaluate all 8 DQ rules for a portfolio's monitored constituents.

    Pure function — does NOT write to the database.  The caller persists
    violations as Alert rows via the alerts service (alerts.create_alert).

    Args:
        db:            SQLAlchemy session (used read-only within this function).
        portfolio_id:  UUID of the portfolio to evaluate.
        price_quotes:  PriceQuote objects returned by the market data adapter.
        fx_quotes:     FxQuote objects returned by the market data adapter.
        as_of:         Evaluation timestamp (UTC-aware; typically datetime.now(UTC)).

    Returns:
        List of DQViolation dataclasses; empty list means data passed all rules.
    """
    violations: list[DQViolation] = []

    # ── Load portfolio ────────────────────────────────────────────────────────
    portfolio = db.query(Portfolio).filter(
        Portfolio.portfolio_id == portfolio_id
    ).first()
    if portfolio is None:
        return violations  # unknown portfolio — nothing to evaluate

    base_currency: str = portfolio.base_currency

    # ── Load monitored constituents ───────────────────────────────────────────
    constituents: list[PortfolioConstituent] = (
        db.query(PortfolioConstituent)
        .filter(
            PortfolioConstituent.portfolio_id == portfolio_id,
            PortfolioConstituent.is_monitored == True,  # noqa: E712
        )
        .all()
    )
    if not constituents:
        return violations

    listing_ids = [str(c.listing_id) for c in constituents]

    # Load listings keyed by listing_id string
    listings: dict[str, InstrumentListing] = {
        str(lst.listing_id): lst
        for lst in db.query(InstrumentListing).filter(
            InstrumentListing.listing_id.in_(listing_ids)
        )
    }

    # ── Index incoming price quotes by listing_id ─────────────────────────────
    quotes_by_listing: dict[str, list[PriceQuote]] = {}
    for q in price_quotes:
        quotes_by_listing.setdefault(q.listing_id, []).append(q)

    # ── Per-listing evaluation ────────────────────────────────────────────────
    for listing_id_str in listing_ids:
        listing = listings.get(listing_id_str)
        if listing is None:
            continue

        # Fetch the 10 most recent PricePoint rows from DB for this listing.
        # We need: latest intraday, latest close (current + one previous) for
        # the staleness / jump checks.
        price_rows: list[PricePoint] = (
            db.query(PricePoint)
            .filter(PricePoint.listing_id == listing.listing_id)
            .order_by(PricePoint.as_of.desc())
            .limit(10)
            .all()
        )

        latest_intraday: Optional[PricePoint] = next(
            (p for p in price_rows if not p.is_close), None
        )
        close_rows = [p for p in price_rows if p.is_close]
        latest_close: Optional[PricePoint] = close_rows[0] if close_rows else None
        prev_close: Optional[PricePoint] = close_rows[1] if len(close_rows) > 1 else None

        # Incoming quotes for this listing
        quotes: list[PriceQuote] = quotes_by_listing.get(listing_id_str, [])
        close_quotes = [q for q in quotes if q.is_close]

        # The most recent incoming quote (any type) for GBX/CCY checks
        latest_quote: Optional[PriceQuote] = (
            max(quotes, key=lambda q: q.as_of) if quotes else None
        )

        # Previous close as Decimal for GBX scale comparison baseline
        prev_close_decimal: Optional[Decimal] = (
            Decimal(str(latest_close.price)) if latest_close else None
        )

        # ── Rule 1: DQ_STALE_INTRADAY ────────────────────────────────────────
        v = check_staleness_intraday(listing, latest_intraday, as_of)
        if v:
            violations.append(v)

        # ── Rule 2: DQ_STALE_CLOSE ───────────────────────────────────────────
        v = check_staleness_close(listing, latest_close, as_of)
        if v:
            violations.append(v)

        # ── Rule 3: DQ_MISSING_CLOSE ─────────────────────────────────────────
        v = check_missing_close(listing, latest_close, as_of)
        if v:
            violations.append(v)

        # ── Rule 4: DQ_JUMP_CLOSE ────────────────────────────────────────────
        # Compare an incoming close quote against the DB latest_close (as
        # "previous"), OR fall back to comparing DB latest vs DB prev.
        if close_quotes and latest_close:
            incoming = max(close_quotes, key=lambda q: q.as_of)
            fake_close = _price_point_from_quote(incoming)
            v = check_price_jump(listing, fake_close, latest_close)
            if v:
                violations.append(v)
        elif latest_close and prev_close:
            v = check_price_jump(listing, latest_close, prev_close)
            if v:
                violations.append(v)

        # ── Rule 5: DQ_GBX_SCALE ─────────────────────────────────────────────
        if latest_quote is not None:
            v = check_gbx_scale(listing, latest_quote, prev_close_decimal)
            if v:
                violations.append(v)

        # ── Rule 6: DQ_CCY_MISMATCH ──────────────────────────────────────────
        if latest_quote is not None:
            v = check_currency_mismatch(listing, latest_quote)
            if v:
                violations.append(v)

        # ── Rule 7: DQ_FX_MISSING ────────────────────────────────────────────
        v = check_fx_missing(listing, base_currency, fx_quotes)
        if v:
            violations.append(v)

        # ── Rule 8: DQ_FX_STALE ──────────────────────────────────────────────
        v = check_fx_stale(listing, base_currency, fx_quotes, as_of)
        if v:
            violations.append(v)

    return violations


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _price_point_from_quote(quote: PriceQuote) -> PricePoint:
    """Build an in-memory (transient) PricePoint from a PriceQuote.

    Uses the SQLAlchemy ORM constructor to ensure _sa_instance_state is
    properly initialised.  This object is intentionally transient --
    it must never be added to a session.
    """
    pp = PricePoint(
        price_point_id=None,
        listing_id=quote.listing_id,
        as_of=quote.as_of,
        price=Decimal(quote.price),
        currency=quote.currency,
        is_close=quote.is_close,
        source_id="",
        raw=quote.raw,
    )
    # created_at is set by server_default; assign manually for in-memory use.
    pp.created_at = quote.as_of
    return pp  # type: ignore[return-value]
