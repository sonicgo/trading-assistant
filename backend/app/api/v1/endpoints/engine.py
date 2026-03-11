"""Engine API endpoints - trade plan generation."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api import deps
from app.domain import models
from app.domain.engine import AssetPosition, RunInputSnapshot
from app.services.engine_calculator import generate_trade_plan
from app.services.engine_inputs import gather_engine_inputs

router = APIRouter()

DRIFT_THRESHOLD_PCT = Decimal("5.0")


class CurrentPosition(BaseModel):
    listing_id: str
    ticker: str
    current_quantity: str
    current_price_gbp: str
    current_value_gbp: str
    target_weight_pct: str
    current_weight_pct: str
    drift_pct: str
    is_drifted: bool


class ProposedTrade(BaseModel):
    action: str
    ticker: str
    listing_id: str
    quantity: str
    estimated_value_gbp: str
    reason: str


class TradePlanResponse(BaseModel):
    portfolio_id: str
    as_of: str

    # Current State
    total_value_gbp: str
    cash_balance_gbp: str
    positions: list[CurrentPosition]

    # Proposed Trades
    trades: list[ProposedTrade]

    # Cash Flow
    projected_post_trade_cash: str
    cash_pool_used: str
    cash_pool_remaining: str

    # Metadata
    warnings: list[str]
    is_blocked: bool
    block_reason: str | None
    block_message: str | None


def _to_str(value: Decimal | float | int | str) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (float, int)):
        return str(value)
    return value


def _to_decimal(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value))


def _build_run_input_snapshot(snapshot_data: dict) -> RunInputSnapshot:
    """Transform engine_inputs snapshot_data into RunInputSnapshot for calculator."""
    portfolio_id = UUID(snapshot_data["portfolio_id"])
    cash_balance_gbp = _to_decimal(snapshot_data["cash_snapshot"]["balance_gbp"])

    # Build asset positions from holding snapshots and allocation map
    positions: list[AssetPosition] = []
    holding_by_listing: dict[str, dict] = {
        h["listing_id"]: h for h in snapshot_data["holding_snapshots"]
    }
    allocation_by_listing: dict[str, dict] = {
        a["listing_id"]: a for a in snapshot_data["allocation_map"]
    }
    price_by_listing: dict[str, dict] = {
        p["listing_id"]: p for p in snapshot_data["price_points_used"]
    }

    # Calculate total portfolio value for weight calculations
    total_value = cash_balance_gbp
    for holding in snapshot_data["holding_snapshots"]:
        price_info = price_by_listing.get(holding["listing_id"])
        if price_info:
            price = _to_decimal(price_info["price"])
            quantity = _to_decimal(holding["quantity"])
            total_value += price * quantity

    # Build positions from holdings that have allocations
    for listing_id, holding in holding_by_listing.items():
        allocation = allocation_by_listing.get(listing_id)
        price_info = price_by_listing.get(listing_id)

        if not allocation or not price_info:
            continue

        ticker = holding.get("ticker") or allocation.get("ticker", "")
        current_quantity = _to_decimal(holding["quantity"])
        current_price_gbp = _to_decimal(price_info["price"])
        current_value_gbp = current_quantity * current_price_gbp
        target_weight_pct = _to_decimal(allocation["target_weight_pct"])

        # Calculate current weight percentage
        if total_value > 0:
            current_weight_pct = (current_value_gbp / total_value) * Decimal("100")
        else:
            current_weight_pct = Decimal("0")

        drift_pct = current_weight_pct - target_weight_pct

        positions.append(
            AssetPosition(
                listing_id=UUID(listing_id),
                ticker=ticker,
                current_quantity=current_quantity,
                current_price_gbp=current_price_gbp,
                current_value_gbp=current_value_gbp,
                target_weight_pct=target_weight_pct,
                current_weight_pct=current_weight_pct,
                drift_pct=drift_pct,
            )
        )

    return RunInputSnapshot(
        portfolio_id=portfolio_id,
        cash_balance_gbp=cash_balance_gbp,
        positions=positions,
    )


@router.get(
    "/{portfolio_id}/engine/plan",
    response_model=TradePlanResponse,
)
def get_trade_plan(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Generate a trade plan for the portfolio (tenancy-checked).
    
    Gathers engine inputs, checks for blocking conditions (frozen, stale prices),
    and generates recommended trades if not blocked.
    """
    as_of = datetime.now(timezone.utc)
    result = gather_engine_inputs(db, str(portfolio_id), as_of)

    if result.is_blocked:
        # Return blocked response without calling calculator
        return TradePlanResponse(
            portfolio_id=str(portfolio_id),
            as_of=as_of.isoformat().replace("+00:00", "Z"),
            total_value_gbp="0",
            cash_balance_gbp="0",
            positions=[],
            trades=[],
            projected_post_trade_cash="0",
            cash_pool_used="0",
            cash_pool_remaining="0",
            warnings=[],
            is_blocked=True,
            block_reason=result.block_reason,
            block_message=result.block_message,
        )

    # Transform snapshot data into RunInputSnapshot
    snapshot_data = result.snapshot_data
    if not snapshot_data:
        return TradePlanResponse(
            portfolio_id=str(portfolio_id),
            as_of=as_of.isoformat().replace("+00:00", "Z"),
            total_value_gbp="0",
            cash_balance_gbp="0",
            positions=[],
            trades=[],
            projected_post_trade_cash="0",
            cash_pool_used="0",
            cash_pool_remaining="0",
            warnings=["No snapshot data available"],
            is_blocked=True,
            block_reason="NO_DATA",
            block_message="Unable to gather snapshot data",
        )

    run_input = _build_run_input_snapshot(snapshot_data)

    # Generate trade plan
    trade_plan = generate_trade_plan(run_input)

    # Calculate total value for response
    total_value = run_input.cash_balance_gbp + sum(
        pos.current_value_gbp for pos in run_input.positions
    )

    # Build current positions response
    positions_response: list[CurrentPosition] = []
    for pos in run_input.positions:
        positions_response.append(
            CurrentPosition(
                listing_id=str(pos.listing_id),
                ticker=pos.ticker,
                current_quantity=_to_str(pos.current_quantity),
                current_price_gbp=_to_str(pos.current_price_gbp),
                current_value_gbp=_to_str(pos.current_value_gbp),
                target_weight_pct=_to_str(pos.target_weight_pct),
                current_weight_pct=_to_str(pos.current_weight_pct),
                drift_pct=_to_str(pos.drift_pct),
                is_drifted=abs(pos.drift_pct) > DRIFT_THRESHOLD_PCT,
            )
        )

    # Build trades response
    trades_response: list[ProposedTrade] = []
    for trade in trade_plan.trades:
        trades_response.append(
            ProposedTrade(
                action=trade.action,
                ticker=trade.ticker,
                listing_id=str(trade.listing_id),
                quantity=_to_str(trade.quantity),
                estimated_value_gbp=_to_str(trade.estimated_value_gbp),
                reason=trade.reason,
            )
        )

    return TradePlanResponse(
        portfolio_id=str(portfolio_id),
        as_of=snapshot_data.get("as_of", as_of.isoformat().replace("+00:00", "Z")),
        total_value_gbp=_to_str(total_value),
        cash_balance_gbp=_to_str(run_input.cash_balance_gbp),
        positions=positions_response,
        trades=trades_response,
        projected_post_trade_cash=_to_str(trade_plan.projected_post_trade_cash),
        cash_pool_used=_to_str(trade_plan.cash_pool_used),
        cash_pool_remaining=_to_str(trade_plan.cash_pool_remaining),
        warnings=trade_plan.warnings,
        is_blocked=False,
        block_reason=None,
        block_message=None,
    )
