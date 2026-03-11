from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import uuid


@dataclass(frozen=True)
class ProposedTrade:
    action: str
    ticker: str
    listing_id: uuid.UUID
    quantity: Decimal
    estimated_value_gbp: Decimal
    reason: str

    def __post_init__(self) -> None:
        if self.action not in ("BUY", "SELL"):
            raise ValueError(f"action must be 'BUY' or 'SELL', got {self.action!r}")
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.estimated_value_gbp < 0:
            raise ValueError(f"estimated_value_gbp cannot be negative, got {self.estimated_value_gbp}")


@dataclass(frozen=True)
class AssetPosition:
    listing_id: uuid.UUID
    ticker: str
    current_quantity: Decimal
    current_price_gbp: Decimal
    current_value_gbp: Decimal
    target_weight_pct: Decimal
    current_weight_pct: Decimal
    drift_pct: Decimal

    def __post_init__(self) -> None:
        if self.current_quantity < 0:
            raise ValueError(f"current_quantity cannot be negative, got {self.current_quantity}")
        if self.current_price_gbp < 0:
            raise ValueError(f"current_price_gbp cannot be negative, got {self.current_price_gbp}")
        if self.current_value_gbp < 0:
            raise ValueError(f"current_value_gbp cannot be negative, got {self.current_value_gbp}")
        if self.target_weight_pct < 0:
            raise ValueError(f"target_weight_pct cannot be negative, got {self.target_weight_pct}")
        if self.current_weight_pct < 0:
            raise ValueError(f"current_weight_pct cannot be negative, got {self.current_weight_pct}")


@dataclass(frozen=True)
class RunInputSnapshot:
    portfolio_id: uuid.UUID
    cash_balance_gbp: Decimal
    positions: list[AssetPosition]
    base_currency: str = "GBP"

    def __post_init__(self) -> None:
        if self.cash_balance_gbp < 0:
            raise ValueError(f"cash_balance_gbp cannot be negative, got {self.cash_balance_gbp}")
        if self.base_currency not in ("GBP", "USD", "EUR"):
            raise ValueError(f"base_currency must be one of GBP, USD, EUR, got {self.base_currency!r}")


@dataclass
class TradePlan:
    trades: list[ProposedTrade] = field(default_factory=list)
    projected_post_trade_cash: Decimal = Decimal("0")
    warnings: list[str] = field(default_factory=list)
    total_value_before: Decimal = Decimal("0")
    total_value_after: Decimal = Decimal("0")
    cash_pool_used: Decimal = Decimal("0")
    cash_pool_remaining: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.projected_post_trade_cash < 0:
            raise ValueError(
                f"projected_post_trade_cash cannot be negative, "
                f"got {self.projected_post_trade_cash}"
            )
        if self.total_value_before < 0:
            raise ValueError(
                f"total_value_before cannot be negative, got {self.total_value_before}"
            )
        if self.total_value_after < 0:
            raise ValueError(
                f"total_value_after cannot be negative, got {self.total_value_after}"
            )
        if self.cash_pool_used < 0:
            raise ValueError(f"cash_pool_used cannot be negative, got {self.cash_pool_used}")
        if self.cash_pool_remaining < 0:
            raise ValueError(
                f"cash_pool_remaining cannot be negative, got {self.cash_pool_remaining}"
            )
