"""
YFinance Market Data Provider - LSE-first UK portfolio adapter.

LSE Rule: bare tickers (no dot) try '<TICKER>.L' first; fall back to bare
ticker when .L returns no data (handles US stocks transparently).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Sequence

import yfinance as yf

from app.services.market_data_adapter import (
    FxQuote,
    InvalidResponseError,
    MarketDataAdapter,
    MarketDataError,
    PriceQuote,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


def _lse_ticker(ticker: str) -> str:
    return ticker if "." in ticker else f"{ticker}.L"


class YFinanceAdapter:

    source_id: str = "yfinance"

    async def fetch_prices(
        self,
        listing_ids: Sequence[str],
        *,
        want_close: bool,
        want_intraday: bool,
    ) -> list[PriceQuote]:
        if not want_close and not want_intraday:
            return []

        results: list[PriceQuote] = []

        for ticker_raw in listing_ids:
            try:
                price, as_of, currency, used_ticker, raw_payload = await asyncio.to_thread(
                    self._fetch_single_price, ticker_raw
                )
            except (ProviderUnavailableError, InvalidResponseError):
                raise
            except Exception as exc:
                raise MarketDataError(
                    f"Unexpected error fetching price for {ticker_raw!r}: {exc}",
                    provider=self.source_id,
                    details={"ticker": ticker_raw, "error": str(exc)},
                ) from exc

            quote_kwargs = dict(
                listing_id=ticker_raw,
                as_of=as_of,
                price=f"{price:.4f}",
                currency=currency,
                raw={**raw_payload, "resolved_ticker": used_ticker},
            )

            if want_close:
                results.append(PriceQuote(**quote_kwargs, is_close=True))
            if want_intraday:
                results.append(PriceQuote(**quote_kwargs, is_close=False))

        return results

    async def fetch_fx_rates(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[FxQuote]:
        results: list[FxQuote] = []

        for base_ccy, quote_ccy in pairs:
            fx_ticker = f"{base_ccy.upper()}{quote_ccy.upper()}=X"
            try:
                rate, as_of, raw_payload = await asyncio.to_thread(
                    self._fetch_fx_rate, fx_ticker
                )
            except (ProviderUnavailableError, InvalidResponseError):
                raise
            except Exception as exc:
                raise MarketDataError(
                    f"Unexpected error fetching FX rate for {fx_ticker!r}: {exc}",
                    provider=self.source_id,
                    details={"pair": fx_ticker, "error": str(exc)},
                ) from exc

            results.append(FxQuote(
                base_ccy=base_ccy.upper(),
                quote_ccy=quote_ccy.upper(),
                as_of=as_of,
                rate=f"{rate:.6f}",
                raw=raw_payload,
            ))

        return results

    def _fetch_single_price(
        self, ticker_raw: str
    ) -> tuple[float, datetime, str | None, str, dict]:
        resolved = _lse_ticker(ticker_raw)
        hist, info = self._download(resolved)

        if (hist is None or hist.empty) and resolved != ticker_raw:
            logger.debug("No data for %s, retrying bare ticker %s", resolved, ticker_raw)
            hist, info = self._download(ticker_raw)
            resolved = ticker_raw

        if hist is None or hist.empty:
            raise InvalidResponseError(
                f"No price data returned for {ticker_raw!r} (tried: {resolved!r})",
                provider=self.source_id,
                details={"ticker": ticker_raw, "resolved": resolved},
            )

        close_price = float(hist["Close"].iloc[-1])
        ts_index = hist.index[-1]

        if hasattr(ts_index, "tzinfo") and ts_index.tzinfo is not None:
            as_of = ts_index.to_pydatetime().astimezone(timezone.utc)
        else:
            as_of = ts_index.to_pydatetime().replace(tzinfo=timezone.utc)

        currency: str | None = info.get("currency") if info else None

        return close_price, as_of, currency, resolved, {
            "source": "yfinance",
            "close": close_price,
            "rows_returned": len(hist),
        }

    def _fetch_fx_rate(self, fx_ticker: str) -> tuple[float, datetime, dict]:
        hist, _ = self._download(fx_ticker)

        if hist is None or hist.empty:
            raise InvalidResponseError(
                f"No FX data returned for {fx_ticker!r}",
                provider=self.source_id,
                details={"fx_ticker": fx_ticker},
            )

        rate = float(hist["Close"].iloc[-1])
        ts_index = hist.index[-1]

        if hasattr(ts_index, "tzinfo") and ts_index.tzinfo is not None:
            as_of = ts_index.to_pydatetime().astimezone(timezone.utc)
        else:
            as_of = ts_index.to_pydatetime().replace(tzinfo=timezone.utc)

        return rate, as_of, {
            "source": "yfinance",
            "fx_ticker": fx_ticker,
            "close": rate,
            "rows_returned": len(hist),
        }

    @staticmethod
    def _download(ticker: str):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            try:
                fast = t.fast_info
                info_dict = {"currency": getattr(fast, "currency", None)}
            except Exception:
                info_dict = {}
            return hist, info_dict
        except Exception as exc:
            raise ProviderUnavailableError(
                f"yfinance request failed for {ticker!r}: {exc}",
                provider="yfinance",
                details={"ticker": ticker, "error": str(exc)},
            ) from exc


YFinanceAdapter: type[MarketDataAdapter]
