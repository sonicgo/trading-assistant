"""
Quick functional smoke-test for all 8 DQ rules.
Run via: docker compose run api python tests/test_dq_rules.py
"""
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.services.data_quality import (
    DQViolation,
    check_staleness_intraday,
    check_staleness_close,
    check_missing_close,
    check_price_jump,
    check_gbx_scale,
    check_currency_mismatch,
    check_fx_missing,
    check_fx_stale,
    _is_market_closed,
)
from app.services.market_data_adapter import FxQuote, PriceQuote

# 5pm UTC = 5pm London time → after 16:30 LSE close
NOW = datetime(2026, 2, 28, 17, 0, 0, tzinfo=timezone.utc)


def make_listing(
    ticker="LLOY",
    exchange="LSE",
    trading_currency="GBX",
    quote_scale="GBX",
    listing_id="00000000-0000-0000-0000-000000000001",
):
    m = MagicMock()
    m.listing_id = listing_id
    m.ticker = ticker
    m.exchange = exchange
    m.trading_currency = trading_currency
    m.quote_scale = quote_scale
    return m


def make_pp(price, as_of, is_close=True):
    pp = MagicMock()
    pp.price = Decimal(str(price))
    pp.as_of = as_of
    pp.is_close = is_close
    return pp


def run_tests():
    listing = make_listing()
    passes = []
    failures = []

    def check(name, condition):
        if condition:
            passes.append(name)
            print(f"PASS: {name}")
        else:
            failures.append(name)
            print(f"FAIL: {name}")

    # ── _is_market_closed ─────────────────────────────────────────────────────
    check(
        "_is_market_closed: LSE closed at 17:00 UTC",
        _is_market_closed("LSE", NOW) is True,
    )
    market_open = datetime(2026, 2, 28, 9, 0, 0, tzinfo=timezone.utc)
    check(
        "_is_market_closed: LSE open at 09:00 UTC",
        _is_market_closed("LSE", market_open) is False,
    )
    check(
        "_is_market_closed: unknown exchange → conservative True",
        _is_market_closed("UNKNOWN_EXCH", NOW) is True,
    )

    # ── Rule 1: DQ_STALE_INTRADAY ─────────────────────────────────────────────
    old_intraday = make_pp(50, NOW - timedelta(hours=2), is_close=False)
    v = check_staleness_intraday(listing, old_intraday, NOW)
    check("DQ_STALE_INTRADAY fires on 2h-old intraday", v is not None and v.rule_code == "DQ_STALE_INTRADAY")

    fresh_intraday = make_pp(50, NOW - timedelta(minutes=5), is_close=False)
    v = check_staleness_intraday(listing, fresh_intraday, NOW)
    check("DQ_STALE_INTRADAY silent for fresh intraday", v is None)

    v = check_staleness_intraday(listing, None, NOW)
    check("DQ_STALE_INTRADAY silent when no intraday exists", v is None)

    # ── Rule 2: DQ_STALE_CLOSE ────────────────────────────────────────────────
    old_close = make_pp(50, NOW - timedelta(days=4))
    v = check_staleness_close(listing, old_close, NOW)
    check("DQ_STALE_CLOSE fires on 4-day-old close (WARN)", v is not None and v.severity == "WARN")

    very_old_close = make_pp(50, NOW - timedelta(days=10))
    v = check_staleness_close(listing, very_old_close, NOW)
    check("DQ_STALE_CLOSE escalates to CRITICAL at 2x threshold", v is not None and v.severity == "CRITICAL")

    fresh_close = make_pp(50, NOW - timedelta(hours=6))
    v = check_staleness_close(listing, fresh_close, NOW)
    check("DQ_STALE_CLOSE silent for fresh close", v is None)

    v = check_staleness_close(listing, None, NOW)
    check("DQ_STALE_CLOSE silent when no close exists (DQ_MISSING handles it)", v is None)

    # ── Rule 3: DQ_MISSING_CLOSE ──────────────────────────────────────────────
    v = check_missing_close(listing, None, NOW)
    check("DQ_MISSING_CLOSE fires after market close with no close", v is not None and v.rule_code == "DQ_MISSING_CLOSE")

    v = check_missing_close(listing, None, market_open)
    check("DQ_MISSING_CLOSE silent during market hours", v is None)

    v = check_missing_close(listing, fresh_close, NOW)
    check("DQ_MISSING_CLOSE silent when close exists", v is None)

    # ── Rule 4: DQ_JUMP_CLOSE ─────────────────────────────────────────────────
    prev_c = make_pp(50, NOW - timedelta(days=1))
    jump_c = make_pp(56, NOW)  # 12% move (> 10% threshold)
    v = check_price_jump(listing, jump_c, prev_c)
    check("DQ_JUMP_CLOSE fires for 12% move", v is not None and v.rule_code == "DQ_JUMP_CLOSE")

    at_threshold_c = make_pp(55, NOW)  # exactly 10% — boundary NOT triggered
    v = check_price_jump(listing, at_threshold_c, prev_c)
    check("DQ_JUMP_CLOSE silent at exactly threshold (boundary: strict >)", v is None)

    normal_c = make_pp(51, NOW)  # 2%
    v = check_price_jump(listing, normal_c, prev_c)
    check("DQ_JUMP_CLOSE silent for 2% move", v is None)

    v = check_price_jump(listing, None, prev_c)
    check("DQ_JUMP_CLOSE silent when no latest_close", v is None)

    # ── Rule 5: DQ_GBX_SCALE ─────────────────────────────────────────────────
    prev_dec = Decimal("50")  # 50p in GBX

    # Provider returned GBP (0.50) instead of GBX (50) — 100x too small
    gbp_quote = PriceQuote(listing_id="...", as_of=NOW, price="0.50", currency="GBP", is_close=False, raw=None)
    v = check_gbx_scale(listing, gbp_quote, prev_dec)
    check("DQ_GBX_SCALE fires: 100x too small (GBP instead of GBX)", v is not None and v.rule_code == "DQ_GBX_SCALE")
    if v:
        check("DQ_GBX_SCALE ratio ~0.01", 0.005 < v.details["ratio"] < 0.02)

    # Provider returned GBX (2800p) instead of GBP (28) — 100x too large
    listing_gbp = make_listing(
        ticker="SHEL", trading_currency="GBP", quote_scale="GBP", listing_id="00000000-0000-0000-0000-000000000002"
    )
    prev_gbp = Decimal("28")
    gbx_quote = PriceQuote(listing_id="...", as_of=NOW, price="2800", currency="GBX", is_close=False, raw=None)
    v = check_gbx_scale(listing_gbp, gbx_quote, prev_gbp)
    check("DQ_GBX_SCALE fires: 100x too large (GBX instead of GBP)", v is not None and v.rule_code == "DQ_GBX_SCALE")
    if v:
        check("DQ_GBX_SCALE ratio ~100", 50 < v.details["ratio"] < 150)

    # Normal price — no violation
    normal_q = PriceQuote(listing_id="...", as_of=NOW, price="51", currency="GBX", is_close=False, raw=None)
    v = check_gbx_scale(listing, normal_q, prev_dec)
    check("DQ_GBX_SCALE silent for normal price (ratio ~1)", v is None)

    v = check_gbx_scale(listing, gbp_quote, None)
    check("DQ_GBX_SCALE silent when no previous close (no baseline)", v is None)

    # ── Rule 6: DQ_CCY_MISMATCH ───────────────────────────────────────────────
    usd_q = PriceQuote(listing_id="...", as_of=NOW, price="51", currency="USD", is_close=False, raw=None)
    v = check_currency_mismatch(listing, usd_q)
    check("DQ_CCY_MISMATCH fires for USD on GBX listing", v is not None and v.rule_code == "DQ_CCY_MISMATCH")

    gbp_q = PriceQuote(listing_id="...", as_of=NOW, price="0.50", currency="GBP", is_close=False, raw=None)
    v = check_currency_mismatch(listing, gbp_q)
    check("DQ_CCY_MISMATCH silent for GBP on GBX (same family)", v is None)

    no_ccy_q = PriceQuote(listing_id="...", as_of=NOW, price="51", currency=None, is_close=False, raw=None)
    v = check_currency_mismatch(listing, no_ccy_q)
    check("DQ_CCY_MISMATCH silent when provider omits currency", v is None)

    # ── Rule 7: DQ_FX_MISSING ─────────────────────────────────────────────────
    usd_listing = make_listing(
        ticker="AAPL", trading_currency="USD", listing_id="00000000-0000-0000-0000-000000000003"
    )

    v = check_fx_missing(usd_listing, "GBP", [])
    check("DQ_FX_MISSING fires: USD listing, no GBP/USD rate", v is not None and v.rule_code == "DQ_FX_MISSING")

    fx_q = FxQuote(base_ccy="GBP", quote_ccy="USD", as_of=NOW, rate="1.27", raw=None)
    v = check_fx_missing(usd_listing, "GBP", [fx_q])
    check("DQ_FX_MISSING silent when FX rate available", v is None)

    # Reverse pair also accepted
    fx_q_rev = FxQuote(base_ccy="USD", quote_ccy="GBP", as_of=NOW, rate="0.79", raw=None)
    v = check_fx_missing(usd_listing, "GBP", [fx_q_rev])
    check("DQ_FX_MISSING silent for reverse pair (USD/GBP)", v is None)

    gbp_listing = make_listing(
        ticker="VOD", trading_currency="GBP", listing_id="00000000-0000-0000-0000-000000000004"
    )
    v = check_fx_missing(gbp_listing, "GBP", [])
    check("DQ_FX_MISSING silent when listing ccy == portfolio base ccy", v is None)

    # GBX listing → normalised to GBP, no FX needed when base is GBP
    v = check_fx_missing(listing, "GBP", [])
    check("DQ_FX_MISSING silent for GBX listing with GBP base (GBX→GBP norm)", v is None)

    # ── Rule 8: DQ_FX_STALE ───────────────────────────────────────────────────
    stale_fx = FxQuote(base_ccy="USD", quote_ccy="GBP", as_of=NOW - timedelta(days=5), rate="1.27", raw=None)
    v = check_fx_stale(usd_listing, "GBP", [stale_fx], NOW)
    check("DQ_FX_STALE fires for 5-day-old FX rate", v is not None and v.rule_code == "DQ_FX_STALE")

    fresh_fx = FxQuote(base_ccy="USD", quote_ccy="GBP", as_of=NOW - timedelta(hours=6), rate="1.27", raw=None)
    v = check_fx_stale(usd_listing, "GBP", [fresh_fx], NOW)
    check("DQ_FX_STALE silent for fresh FX rate", v is None)

    v = check_fx_stale(usd_listing, "GBP", [], NOW)
    check("DQ_FX_STALE silent when no matching pair (DQ_FX_MISSING handles it)", v is None)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print(f"Results: {len(passes)} passed, {len(failures)} failed")
    if failures:
        print("FAILED tests:", failures)
        raise SystemExit(1)
    else:
        print("=== ALL DQ RULE TESTS PASSED ===")


if __name__ == "__main__":
    run_tests()
