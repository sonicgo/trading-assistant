"""
Market Data Adapter Interface

Defines the abstract contract for market data providers to enable
provider independence and testability.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence
from decimal import Decimal


@dataclass(frozen=True)
class PriceQuote:
    """A price quote from a market data provider.
    
    Attributes:
        listing_id: UUID of the instrument listing
        as_of: Timestamp when the price was recorded
        price: Price value as decimal string for precision
        currency: Currency code (e.g., GBP, USD) if provider-reported
        is_close: True if this is an EOD close price, False for intraday
        raw: Optional raw provider payload for audit/debug
    """
    listing_id: str
    as_of: datetime
    price: str  # decimal string
    currency: str | None  # provider-reported if available
    is_close: bool
    raw: dict | None


@dataclass(frozen=True)
class FxQuote:
    """An FX rate quote from a market data provider.
    
    Attributes:
        base_ccy: Base currency code (e.g., GBP)
        quote_ccy: Quote currency code (e.g., USD)
        as_of: Timestamp when the rate was recorded
        rate: Exchange rate as decimal string for precision
        raw: Optional raw provider payload for audit/debug
    """
    base_ccy: str
    quote_ccy: str
    as_of: datetime
    rate: str  # decimal string
    raw: dict | None


class MarketDataAdapter(Protocol):
    """Protocol defining the market data provider interface.
    
    Implementations must be provider-agnostic from the consumer's perspective.
    All methods are async to support I/O-bound operations.
    """
    
    source_id: str
    """Unique identifier for this provider (e.g., 'mock', 'yahoo', 'alphavantage')."""
    
    async def fetch_prices(
        self,
        listing_ids: Sequence[str],
        *,
        want_close: bool,
        want_intraday: bool,
    ) -> list[PriceQuote]:
        """Fetch price quotes for the given listings.
        
        Args:
            listing_ids: List of listing UUIDs to fetch prices for
            want_close: Whether to include EOD close prices
            want_intraday: Whether to include intraday prices
            
        Returns:
            List of PriceQuote objects (may be empty if no data available)
            
        Raises:
            MarketDataError: If the provider request fails
        """
        ...
    
    async def fetch_fx_rates(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[FxQuote]:
        """Fetch FX rates for the given currency pairs.
        
        Args:
            pairs: List of (base_ccy, quote_ccy) tuples
            
        Returns:
            List of FxQuote objects (may be empty if no data available)
            
        Raises:
            MarketDataError: If the provider request fails
        """
        ...


class MarketDataError(Exception):
    """Base exception for market data provider errors."""
    
    def __init__(self, message: str, provider: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.provider = provider
        self.details = details or {}


class ProviderUnavailableError(MarketDataError):
    """Raised when the market data provider is unavailable."""
    pass


class InvalidResponseError(MarketDataError):
    """Raised when the provider returns invalid/unparseable data."""
    pass


class RateLimitError(MarketDataError):
    """Raised when the provider rate limit is exceeded."""
    pass
