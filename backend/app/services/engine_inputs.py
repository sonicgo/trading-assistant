from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
import uuid

from sqlalchemy import true
from sqlalchemy.orm import Session

from app.domain.models import (
    CashSnapshot,
    FreezeState,
    HoldingSnapshot,
    PortfolioPolicyAllocation,
    PricePoint,
)


PRICE_STALENESS_DAYS = 3
PRICE_STALENESS_THRESHOLD = timedelta(days=PRICE_STALENESS_DAYS)


@dataclass
class EngineInputResult:
    is_blocked: bool
    block_reason: Optional[str]
    block_message: Optional[str]
    snapshot_data: Optional[dict[str, Any]]


class StalePriceError(Exception):
    def __init__(self, ticker: str, age: timedelta) -> None:
        self.ticker = ticker
        self.age = age
        age_days = age.total_seconds() / 86_400
        super().__init__(
            f"Stale market data for {ticker}; latest trusted price is older than "
            f"{PRICE_STALENESS_DAYS} days (age={age_days:.2f}d)"
        )


def gather_engine_inputs(
    db: Session,
    portfolio_id: str,
    as_of: datetime,
) -> EngineInputResult:
    portfolio_uuid = uuid.UUID(str(portfolio_id))
    as_of_utc = _as_utc(as_of)

    active_freeze = (
        db.query(FreezeState)
        .filter(
            FreezeState.portfolio_id == portfolio_uuid,
            FreezeState.is_frozen == true(),
            FreezeState.cleared_at.is_(None),
        )
        .order_by(FreezeState.created_at.desc())
        .first()
    )
    if active_freeze is not None:
        return EngineInputResult(
            is_blocked=True,
            block_reason="FROZEN",
            block_message="Portfolio is currently frozen and cannot run recommendations",
            snapshot_data=None,
        )

    cash_snapshot = (
        db.query(CashSnapshot)
        .filter(CashSnapshot.portfolio_id == portfolio_uuid)
        .first()
    )

    holding_snapshots = (
        db.query(HoldingSnapshot)
        .filter(HoldingSnapshot.portfolio_id == portfolio_uuid)
        .all()
    )

    policy_allocations = (
        db.query(PortfolioPolicyAllocation)
        .filter(PortfolioPolicyAllocation.portfolio_id == portfolio_uuid)
        .all()
    )
    ticker_by_listing: dict[uuid.UUID, str] = {
        allocation.listing_id: allocation.ticker for allocation in policy_allocations
    }

    stale_cutoff = as_of_utc - PRICE_STALENESS_THRESHOLD
    price_points_used: list[dict[str, Any]] = []

    for holding in holding_snapshots:
        latest_close = (
            db.query(PricePoint)
            .filter(
                PricePoint.listing_id == holding.listing_id,
                PricePoint.is_close == true(),
            )
            .order_by(PricePoint.as_of.desc())
            .first()
        )

        ticker = ticker_by_listing.get(holding.listing_id, str(holding.listing_id))

        if latest_close is None:
            return EngineInputResult(
                is_blocked=True,
                block_reason="MISSING_PRICE",
                block_message=(
                    f"Missing trusted close price for {ticker}; run is blocked"
                ),
                snapshot_data=None,
            )

        latest_close_as_of = _as_utc(latest_close.as_of)
        if latest_close_as_of < stale_cutoff:
            stale_error = StalePriceError(
                ticker=ticker,
                age=as_of_utc - latest_close_as_of,
            )
            return EngineInputResult(
                is_blocked=True,
                block_reason="STALE_PRICE",
                block_message=(
                    f"Stale market data for {stale_error.ticker}; "
                    f"latest trusted price is older than {PRICE_STALENESS_DAYS} days"
                ),
                snapshot_data=None,
            )

        price_points_used.append(
            {
                "listing_id": str(latest_close.listing_id),
                "ticker": ticker,
                "as_of": _isoformat(latest_close_as_of),
                "price": _to_str(latest_close.price),
                "currency": latest_close.currency,
                "is_close": latest_close.is_close,
            }
        )

    snapshot_data = {
        "portfolio_id": str(portfolio_uuid),
        "as_of": _isoformat(as_of_utc),
        "cash_snapshot": {
            "balance_gbp": _to_str(cash_snapshot.balance_gbp) if cash_snapshot else _to_str(Decimal("0")),
            "updated_at": _isoformat(cash_snapshot.updated_at) if cash_snapshot else None,
        },
        "holding_snapshots": [
            {
                "portfolio_id": str(holding.portfolio_id),
                "listing_id": str(holding.listing_id),
                "ticker": ticker_by_listing.get(holding.listing_id),
                "quantity": _to_str(holding.quantity),
                "book_cost_gbp": _to_str(holding.book_cost_gbp),
                "avg_cost_gbp": _to_str(holding.avg_cost_gbp),
                "updated_at": _isoformat(holding.updated_at),
            }
            for holding in holding_snapshots
        ],
        "price_points_used": price_points_used,
        "allocation_map": [
            {
                "listing_id": str(allocation.listing_id),
                "ticker": allocation.ticker,
                "sleeve_code": allocation.sleeve_code,
                "policy_role": allocation.policy_role,
                "target_weight_pct": _to_str(allocation.target_weight_pct),
                "priority_rank": allocation.priority_rank,
                "policy_hash": allocation.policy_hash,
            }
            for allocation in policy_allocations
        ],
        "gates": {
            "is_frozen": False,
            "dq_ok": True,
        },
    }

    return EngineInputResult(
        is_blocked=False,
        block_reason=None,
        block_message=None,
        snapshot_data=snapshot_data,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)
