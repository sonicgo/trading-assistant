"""
YFinance Market Data Provider - LSE-first UK portfolio adapter.

LSE Rule: bare tickers (no dot) try '<TICKER>.L' first; fall back to bare
ticker when .L returns no data (handles US stocks transparently).
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

import pandas as pd
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

    def fetch_prices_batch(
        self,
        tickers: list[str],
    ) -> dict[str, tuple[Decimal, datetime, str | None]]:
        """
        Fetch prices for multiple tickers in a single batch request.

        Applies LSE .L suffix rule to tickers, downloads all at once
        using yf.download(), and returns a dictionary mapping original
        ticker strings to (price, as_of, currency) tuples.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker -> (price, as_of, currency)
        """
        if not tickers:
            return {}

        # Build mapping: resolved (Yahoo) symbol -> original ticker
        resolved_to_original: dict[str, str] = {}
        resolved_tickers: list[str] = []
        for ticker in tickers:
            resolved = _lse_ticker(ticker)
            resolved_tickers.append(resolved)
            resolved_to_original[resolved] = ticker

        ticker_string = " ".join(resolved_tickers)
        logger.info(f"Batch fetching {len(tickers)} tickers: {ticker_string}")

        results: dict[str, tuple[Decimal, datetime, str | None]] = {}

        # Try to fetch intraday data first (1-minute interval for live prices)
        try:
            data = yf.download(
                ticker_string,
                period="1d",
                interval="1m",
                progress=False,
            )
            intraday_success = True
        except Exception as exc:
            logger.warning(f"Intraday fetch failed, falling back to daily: {exc}")
            intraday_success = False
            data = None

        # Fallback to daily data if intraday fails
        if not intraday_success or data is None or data.empty:
            try:
                data = yf.download(
                    ticker_string,
                    period="5d",
                    progress=False,
                )
            except Exception as exc:
                raise ProviderUnavailableError(
                    f"yfinance batch download failed: {exc}",
                    provider="yfinance",
                    details={"tickers": tickers, "error": str(exc)},
                ) from exc

        if data is None or data.empty:
            logger.warning("yfinance returned empty data for batch request")
            return results

        is_multiindex = isinstance(data.columns, pd.MultiIndex)
        logger.debug(f"DataFrame columns type: {type(data.columns)}, is_multiindex: {is_multiindex}, intraday: {intraday_success}")

        if is_multiindex:
            if "Close" not in data.columns.get_level_values(0) and "Adj Close" not in data.columns.get_level_values(0):
                logger.warning("No 'Close' or 'Adj Close' price type in MultiIndex data")
                return results
            available_tickers = data["Close"].columns.tolist() if "Close" in data.columns.get_level_values(0) else data["Adj Close"].columns.tolist()
            close_df = data["Close"] if "Close" in data.columns.get_level_values(0) else data["Adj Close"]
            adj_close_df = data["Adj Close"] if "Adj Close" in data.columns.get_level_values(0) else None
        else:
            if "Close" not in data.columns and "Adj Close" not in data.columns:
                logger.warning("No 'Close' or 'Adj Close' column in flat data")
                return results
            available_tickers = [resolved_tickers[0]] if len(tickers) == 1 else []
            price_col = "Close" if "Close" in data.columns else "Adj Close"
            close_df = data[[price_col]].rename(columns={price_col: resolved_tickers[0]}) if len(tickers) == 1 else pd.DataFrame()
            adj_close_df = data[["Adj Close"]].rename(columns={"Adj Close": resolved_tickers[0]}) if "Adj Close" in data.columns and len(tickers) == 1 else None

        # Track which tickers were successfully parsed
        parsed_tickers = set()

        for resolved, original in resolved_to_original.items():
            try:
                if resolved not in available_tickers:
                    logger.warning(f"Ticker {original} (resolved: {resolved}) not found in response columns: {available_tickers}")
                    continue

                close_series = close_df[resolved].dropna()

                if close_series.empty and adj_close_df is not None:
                    close_series = adj_close_df[resolved].dropna()
                    logger.debug(f"Using Adj Close for {original} (resolved: {resolved}) since Close was empty")

                if close_series.empty:
                    logger.warning(f"No valid close prices for {original} (resolved: {resolved})")
                    continue

                raw_price = close_series.iloc[-1]
                ts_index = close_series.index[-1]

                if pd.isna(raw_price) or (isinstance(raw_price, float) and math.isnan(raw_price)):
                    logger.warning(f"Price data for {original} is NaN, trying earlier data points")
                    found_valid = False
                    for idx in range(-2, -min(len(close_series) + 1, 6), -1):
                        try:
                            alt_price = close_series.iloc[idx]
                            alt_ts = close_series.index[idx]
                            if not pd.isna(alt_price) and not (isinstance(alt_price, float) and math.isnan(alt_price)):
                                raw_price = alt_price
                                ts_index = alt_ts
                                logger.debug(f"Using price from {idx} periods ago for {original}")
                                found_valid = True
                                break
                        except IndexError:
                            break
                    if not found_valid:
                        logger.warning(f"All price data for {original} is NaN, will try fallback")
                        continue

                price = Decimal(str(raw_price))

                # Use the timestamp from the data (intraday gives precise timestamps)
                if hasattr(ts_index, "tzinfo") and ts_index.tzinfo is not None:
                    as_of = ts_index.to_pydatetime().astimezone(timezone.utc)
                else:
                    as_of = ts_index.to_pydatetime().replace(tzinfo=timezone.utc)

                currency = self._get_currency(resolved)
                results[original] = (price, as_of, currency)
                parsed_tickers.add(original)
                logger.debug(f"Successfully parsed price for {original}: {price} {currency} at {as_of}")

            except Exception as exc:
                logger.warning(f"Failed to parse data for {original} (resolved: {resolved}): {exc}")
                continue

        # Fallback for missing tickers (e.g., IGL5) using fast_info
        missing_tickers = set(resolved_to_original.values()) - parsed_tickers
        for original in missing_tickers:
            try:
                resolved = _lse_ticker(original)
                logger.info(f"Attempting fast_info fallback for {original} (resolved: {resolved})")

                ticker_obj = yf.Ticker(resolved)
                fast_info = ticker_obj.fast_info

                if fast_info and hasattr(fast_info, 'last_price') and fast_info.last_price:
                    price = Decimal(str(fast_info.last_price))
                    as_of = datetime.now(timezone.utc)
                    currency = getattr(fast_info, 'currency', None)

                    results[original] = (price, as_of, currency)
                    logger.info(f"Successfully fetched {original} via fast_info: {price} {currency}")
                else:
                    logger.warning(f"No fast_info available for {original}")
            except Exception as exc:
                logger.warning(f"Fast_info fallback failed for {original}: {exc}")
                continue

        return results

    def _get_currency(self, ticker: str) -> str | None:
        """Get currency for a ticker (best effort)."""
        try:
            t = yf.Ticker(ticker)
            fast = t.fast_info
            return getattr(fast, "currency", None)
        except Exception:
            return None

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
