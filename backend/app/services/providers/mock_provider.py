"""
Mock Market Data Provider

A deterministic mock implementation of MarketDataAdapter for:
- Development without external API dependencies
- Repeatable testing with known price values
- DQ gate testing via configurable anomalies
"""
from datetime import datetime, timezone
from typing import Sequence
import uuid

from app.services.market_data_adapter import (
    MarketDataAdapter,
    PriceQuote,
    FxQuote,
    MarketDataError,
)


class MockProvider:
    """Mock market data provider returning deterministic values.
    
    Prices are generated deterministically based on listing_id hash
    to ensure the same listing always returns the same price for
    reproducible tests.
    
    Supports anomaly injection for testing the DQ gate:
    - stale_prices: Return prices from the past
    - jump_prices: Return prices with large jumps
    - scale_mismatch: Return prices in wrong currency scale
    """
    
    source_id: str = "mock"
    
    def __init__(
        self,
        stale_prices: bool = False,
        jump_prices: bool = False,
        scale_mismatch: bool = False,
        fixed_as_of: "datetime | None" = None,
    ):
        """Initialize mock provider with optional anomaly flags.
        
        Args:
            stale_prices: If True, return prices from 7 days ago
            jump_prices: If True, return prices 10x higher than normal
            scale_mismatch: If True, return GBX prices as GBP (100x)
            fixed_as_of: If set, always use this timestamp (idempotency tests)
        """
        self.stale_prices = stale_prices
        self.jump_prices = jump_prices
        self.scale_mismatch = scale_mismatch
        self.fixed_as_of = fixed_as_of
    
    def _generate_price(self, listing_id: str) -> tuple[float, str]:
        """Generate a deterministic price for a listing.
        
        Uses the listing_id UUID to generate consistent mock prices
        in a realistic range (10.0 to 500.0).
        
        Returns:
            Tuple of (price, currency)
        """
        # Use UUID bytes to generate deterministic but varied prices
        uuid_bytes = uuid.UUID(listing_id).bytes
        # Map first 4 bytes to price range 10.0 - 500.0
        price_base = int.from_bytes(uuid_bytes[:4], 'big') % 49000
        price = 10.0 + (price_base / 100.0)
        
        # Apply anomaly modifiers
        if self.jump_prices:
            price = price * 10.0
        
        # Currency based on listing_id hash (mostly GBP for V1)
        currency = "GBP" if uuid_bytes[0] % 4 != 0 else "USD"
        
        return price, currency
    
    def _get_timestamp(self) -> datetime:
        """Get current timestamp, or stale/fixed timestamp if configured."""
        if self.fixed_as_of is not None:
            return self.fixed_as_of
        if self.stale_prices:
            # Return timestamp from 7 days ago
            from datetime import timedelta
            return datetime.now(timezone.utc) - timedelta(days=7)
        return datetime.now(timezone.utc)
    
    async def fetch_prices(
        self,
        listing_ids: Sequence[str],
        *,
        want_close: bool,
        want_intraday: bool,
    ) -> list[PriceQuote]:
        """Fetch mock price quotes.
        
        Returns deterministic prices for each listing_id.
        Supports close and intraday requests (returns same price for both
        in mock, differentiated by is_close flag).
        """
        results: list[PriceQuote] = []
        timestamp = self._get_timestamp()
        
        for listing_id in listing_ids:
            try:
                price_val, currency = self._generate_price(listing_id)
                
                # Apply scale mismatch anomaly (return GBX as GBP = 100x)
                if self.scale_mismatch and currency == "GBP":
                    # Simulate GBX/GBP confusion by multiplying by 100
                    price_val = price_val * 100
                
                # Create close price if requested
                if want_close:
                    results.append(PriceQuote(
                        listing_id=listing_id,
                        as_of=timestamp,
                        price=f"{price_val:.4f}",
                        currency=currency,
                        is_close=True,
                        raw={
                            "mock": True,
                            "anomaly_stale": self.stale_prices,
                            "anomaly_jump": self.jump_prices,
                            "anomaly_scale": self.scale_mismatch,
                        }
                    ))
                
                # Create intraday price if requested
                if want_intraday:
                    # Intraday price is slightly different (up to 1% variance)
                    import random
                    random.seed(listing_id)  # Deterministic variance
                    variance = 1.0 + (random.random() * 0.02 - 0.01)
                    intraday_price = price_val * variance
                    
                    results.append(PriceQuote(
                        listing_id=listing_id,
                        as_of=timestamp,
                        price=f"{intraday_price:.4f}",
                        currency=currency,
                        is_close=False,
                        raw={
                            "mock": True,
                            "variance": f"{variance:.4f}",
                        }
                    ))
                    
            except ValueError as e:
                # Invalid listing_id format
                raise MarketDataError(
                    f"Invalid listing_id format: {listing_id}",
                    provider=self.source_id,
                    details={"error": str(e)}
                )
        
        return results
    
    async def fetch_fx_rates(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[FxQuote]:
        """Fetch mock FX rates.
        
        Returns deterministic rates for common currency pairs:
        - GBP/USD: ~1.27
        - USD/GBP: ~0.79
        - EUR/GBP: ~0.85
        - Other pairs: generated deterministically
        """
        results: list[FxQuote] = []
        timestamp = self._get_timestamp()
        
        # Base rates for common pairs
        base_rates: dict[tuple[str, str], float] = {
            ("GBP", "USD"): 1.27,
            ("USD", "GBP"): 0.79,
            ("EUR", "GBP"): 0.85,
            ("GBP", "EUR"): 1.18,
            ("USD", "EUR"): 0.92,
            ("EUR", "USD"): 1.09,
        }
        
        for base_ccy, quote_ccy in pairs:
            pair = (base_ccy.upper(), quote_ccy.upper())
            
            # Get base rate or generate deterministic one
            if pair in base_rates:
                rate = base_rates[pair]
            else:
                # Generate deterministic rate for unknown pairs
                # Using hash of currency codes
                hash_val = hash(f"{pair[0]}{pair[1]}") % 10000
                rate = 0.5 + (hash_val / 10000.0) * 2.0  # Range: 0.5 - 2.5
            
            results.append(FxQuote(
                base_ccy=pair[0],
                quote_ccy=pair[1],
                as_of=timestamp,
                rate=f"{rate:.6f}",
                raw={
                    "mock": True,
                    "source": "deterministic",
                }
            ))
        
        return results


# Type alias for protocol compliance
MockProvider: type[MarketDataAdapter]
