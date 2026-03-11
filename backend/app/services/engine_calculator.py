from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.domain.engine import AssetPosition, ProposedTrade, RunInputSnapshot, TradePlan


DRIFT_THRESHOLD_PCT = Decimal("5.0")
MIN_TRADE_SIZE_GBP = Decimal("500")
MAX_SELL_ORDERS = 2
MAX_BUY_ORDERS = 3

PRECISION = Decimal("0.0000000001")
HUNDRED = Decimal("100")


def generate_trade_plan(
    snapshot: RunInputSnapshot,
    drift_threshold: Decimal = DRIFT_THRESHOLD_PCT,
    min_trade_size: Decimal = MIN_TRADE_SIZE_GBP,
    max_sells: int = MAX_SELL_ORDERS,
    max_buys: int = MAX_BUY_ORDERS,
) -> TradePlan:
    warnings: list[str] = []
    candidate_trades: list[ProposedTrade] = []

    positions = list(snapshot.positions)
    total_positions_value = _q(
        sum((position.current_value_gbp for position in positions), Decimal("0")),
        PRECISION,
    )
    total_value = _q(snapshot.cash_balance_gbp + total_positions_value, PRECISION)

    if total_value <= 0:
        warnings.append("Total portfolio value is zero; no trades generated")
        return TradePlan(
            trades=[],
            projected_post_trade_cash=_q(snapshot.cash_balance_gbp, PRECISION),
            warnings=warnings,
            total_value_before=_q(total_value, PRECISION),
            total_value_after=_q(total_value, PRECISION),
            cash_pool_used=Decimal("0"),
            cash_pool_remaining=_q(snapshot.cash_balance_gbp, PRECISION),
        )

    analyzed_positions = [_analyze_position(position, total_value) for position in positions]

    overweight = [
        analyzed for analyzed in analyzed_positions if analyzed["drift_pct"] > drift_threshold
    ]
    underweight = [
        analyzed for analyzed in analyzed_positions if analyzed["drift_pct"] < -drift_threshold
    ]

    overweight.sort(
        key=lambda item: (
            -item["drift_pct"],
            item["position"].ticker,
            str(item["position"].listing_id),
        )
    )
    underweight.sort(
        key=lambda item: (
            item["drift_pct"],
            item["position"].ticker,
            str(item["position"].listing_id),
        )
    )

    projected_cash_pool = _q(snapshot.cash_balance_gbp, PRECISION)

    if len(overweight) > max_sells:
        warnings.append(
            f"Overweight assets exceed sell cap ({max_sells}); limiting sells to highest drift"
        )

    for analyzed in overweight[:max_sells]:
        position = analyzed["position"]
        target_value = _q((position.target_weight_pct / HUNDRED) * total_value, PRECISION)
        excess_value = _q(position.current_value_gbp - target_value, PRECISION)

        if excess_value <= 0:
            continue
        if position.current_price_gbp <= 0:
            warnings.append(
                f"Skipped SELL for {position.ticker}: current_price_gbp is zero"
            )
            continue

        quantity_to_sell = _q(excess_value / position.current_price_gbp, PRECISION)
        if quantity_to_sell <= 0:
            continue

        sell_value = _q(quantity_to_sell * position.current_price_gbp, PRECISION)
        candidate_trades.append(
            ProposedTrade(
                action="SELL",
                ticker=position.ticker,
                listing_id=position.listing_id,
                quantity=quantity_to_sell,
                estimated_value_gbp=sell_value,
                reason="DRIFT_ABOVE_THRESHOLD",
            )
        )
        projected_cash_pool = _q(projected_cash_pool + sell_value, PRECISION)

    if len(underweight) > max_buys:
        warnings.append(
            f"Underweight assets exceed buy cap ({max_buys}); limiting buys to lowest drift"
        )

    for analyzed in underweight[:max_buys]:
        if projected_cash_pool <= 0:
            warnings.append("Buy execution stopped: projected cash pool exhausted")
            break

        position = analyzed["position"]
        target_value = _q((position.target_weight_pct / HUNDRED) * total_value, PRECISION)
        deficit_value = _q(target_value - position.current_value_gbp, PRECISION)

        if deficit_value <= 0:
            continue
        if position.current_price_gbp <= 0:
            warnings.append(
                f"Skipped BUY for {position.ticker}: current_price_gbp is zero"
            )
            continue

        buy_value = _q(min(deficit_value, projected_cash_pool), PRECISION)
        if buy_value <= 0:
            continue

        quantity_to_buy = _q(buy_value / position.current_price_gbp, PRECISION)
        if quantity_to_buy <= 0:
            continue

        buy_value = _q(quantity_to_buy * position.current_price_gbp, PRECISION)
        candidate_trades.append(
            ProposedTrade(
                action="BUY",
                ticker=position.ticker,
                listing_id=position.listing_id,
                quantity=quantity_to_buy,
                estimated_value_gbp=buy_value,
                reason="DRIFT_BELOW_THRESHOLD",
            )
        )
        projected_cash_pool = _q(projected_cash_pool - buy_value, PRECISION)

    trades: list[ProposedTrade] = []
    filtered_count = 0
    for trade in candidate_trades:
        if trade.estimated_value_gbp < min_trade_size:
            filtered_count += 1
            continue
        trades.append(trade)

    if filtered_count > 0:
        warnings.append(
            f"Filtered out {filtered_count} trade(s) below minimum size {min_trade_size} GBP"
        )

    total_sell_value = _q(
        sum(
            (trade.estimated_value_gbp for trade in trades if trade.action == "SELL"),
            Decimal("0"),
        ),
        PRECISION,
    )
    total_buy_value = _q(
        sum(
            (trade.estimated_value_gbp for trade in trades if trade.action == "BUY"),
            Decimal("0"),
        ),
        PRECISION,
    )

    projected_post_trade_cash = _q(
        snapshot.cash_balance_gbp + total_sell_value - total_buy_value,
        PRECISION,
    )
    cash_pool_used = _q(total_buy_value, PRECISION)
    cash_pool_remaining = _q(projected_post_trade_cash, PRECISION)

    return TradePlan(
        trades=trades,
        projected_post_trade_cash=projected_post_trade_cash,
        warnings=warnings,
        total_value_before=total_value,
        total_value_after=total_value,
        cash_pool_used=cash_pool_used,
        cash_pool_remaining=cash_pool_remaining,
    )


def _analyze_position(position: AssetPosition, total_value: Decimal) -> dict[str, Decimal | AssetPosition]:
    current_weight_pct = _q((position.current_value_gbp / total_value) * HUNDRED, PRECISION)
    drift_pct = _q(current_weight_pct - position.target_weight_pct, PRECISION)
    return {
        "position": position,
        "current_weight_pct": current_weight_pct,
        "drift_pct": drift_pct,
    }


def _q(value: Decimal, precision: Decimal) -> Decimal:
    return value.quantize(precision, rounding=ROUND_HALF_UP)
