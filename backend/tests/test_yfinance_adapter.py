import re
from decimal import Decimal, InvalidOperation

import pytest
import pytest_asyncio

from app.services.providers.yfinance_adapter import YFinanceAdapter, _lse_ticker


class TestLseTickerRule:
    def test_bare_ticker_gets_lse_suffix(self):
        assert _lse_ticker("VWRP") == "VWRP.L"

    def test_bare_ticker_igl5(self):
        assert _lse_ticker("IGL5") == "IGL5.L"

    def test_already_suffixed_ticker_unchanged(self):
        assert _lse_ticker("VWRP.L") == "VWRP.L"

    def test_us_style_ticker_gets_lse_suffix_initially(self):
        assert _lse_ticker("AAPL") == "AAPL.L"

    def test_ticker_with_other_suffix_unchanged(self):
        assert _lse_ticker("IGL5.AS") == "IGL5.AS"


@pytest.mark.asyncio
class TestYFinanceAdapterLive:
    async def test_fetch_vwrp_close_price(self):
        adapter = YFinanceAdapter()
        quotes = await adapter.fetch_prices(["VWRP"], want_close=True, want_intraday=False)

        assert len(quotes) == 1
        q = quotes[0]
        assert q.listing_id == "VWRP"
        assert q.is_close is True
        assert q.raw["resolved_ticker"] == "VWRP.L"

        price = Decimal(q.price)
        assert price > Decimal("0"), f"Expected positive price, got {price}"
        assert re.match(r"^\d+\.\d{4}$", q.price), f"Price not in 4dp format: {q.price!r}"

        print(f"\nLive VWRP price: {q.price} {q.currency} @ {q.as_of}")

    async def test_fetch_vwrp_price_is_decimal_compatible(self):
        adapter = YFinanceAdapter()
        quotes = await adapter.fetch_prices(["VWRP"], want_close=True, want_intraday=False)
        assert quotes
        try:
            Decimal(quotes[0].price)
        except InvalidOperation:
            pytest.fail(f"Price {quotes[0].price!r} is not a valid Decimal string")

    async def test_want_close_false_and_intraday_false_returns_empty(self):
        adapter = YFinanceAdapter()
        quotes = await adapter.fetch_prices(["VWRP"], want_close=False, want_intraday=False)
        assert quotes == []

    async def test_fetch_gbpusd_fx_rate(self):
        adapter = YFinanceAdapter()
        fx_quotes = await adapter.fetch_fx_rates([("GBP", "USD")])

        assert len(fx_quotes) == 1
        q = fx_quotes[0]
        assert q.base_ccy == "GBP"
        assert q.quote_ccy == "USD"
        rate = Decimal(q.rate)
        assert rate > Decimal("0.5"), f"Unexpected GBP/USD rate: {rate}"
        print(f"\nLive GBP/USD rate: {q.rate} @ {q.as_of}")
