import uuid
from decimal import Decimal

from app.domain.engine import AssetPosition, RunInputSnapshot
from app.services.engine_calculator import generate_trade_plan


def create_position(
    ticker: str,
    quantity: Decimal,
    price: Decimal,
    target_weight: Decimal,
    current_weight: Decimal,
) -> AssetPosition:
    return AssetPosition(
        listing_id=uuid.uuid4(),
        ticker=ticker,
        current_quantity=quantity,
        current_price_gbp=price,
        current_value_gbp=quantity * price,
        target_weight_pct=target_weight,
        current_weight_pct=current_weight,
        drift_pct=current_weight - target_weight,
    )


def create_test_snapshot(
    cash: float,
    positions: list[tuple[str, float, float, float, float]],
) -> RunInputSnapshot:
    parsed_positions = [
        create_position(
            ticker=ticker,
            quantity=Decimal(str(quantity)),
            price=Decimal(str(price)),
            target_weight=Decimal(str(target_weight)),
            current_weight=Decimal(str(current_weight)),
        )
        for ticker, quantity, price, target_weight, current_weight in positions
    ]
    return RunInputSnapshot(
        portfolio_id=uuid.uuid4(),
        cash_balance_gbp=Decimal(str(cash)),
        positions=parsed_positions,
        base_currency="GBP",
    )


def create_test_snapshot_with_many_overweight() -> RunInputSnapshot:
    return create_test_snapshot(
        cash=0,
        positions=[
            ("OW1", 200, 10.0, 10.0, 20.0),
            ("OW2", 190, 10.0, 10.0, 19.0),
            ("OW3", 180, 10.0, 10.0, 18.0),
            ("OW4", 170, 10.0, 10.0, 17.0),
            ("OW5", 160, 10.0, 10.0, 16.0),
            ("BAL", 100, 10.0, 50.0, 10.0),
        ],
    )


def create_test_snapshot_with_many_underweight() -> RunInputSnapshot:
    return create_test_snapshot(
        cash=0,
        positions=[
            ("UW1", 20, 10.0, 10.0, 2.0),
            ("UW2", 30, 10.0, 10.0, 3.0),
            ("UW3", 40, 10.0, 10.0, 4.0),
            ("UW4", 50, 10.0, 10.0, 5.0),
            ("UW5", 60, 10.0, 10.0, 6.0),
            ("BAL", 800, 10.0, 50.0, 80.0),
        ],
    )


def test_no_trades_when_drift_under_threshold():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("VWRP", 320, 10.0, 35.0, 32.0),
            ("SEMI", 380, 10.0, 35.0, 38.0),
            ("BOND", 300, 10.0, 30.0, 30.0),
        ],
    )

    plan = generate_trade_plan(snapshot)

    assert len(plan.trades) == 0
    assert plan.cash_pool_used == Decimal("0")


def test_drops_trades_under_500_gbp():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("VWRP", 2800, 1.0, 50.0, 56.0),
            ("SEMI", 2200, 1.0, 50.0, 44.0),
        ],
    )

    plan = generate_trade_plan(snapshot)

    assert len(plan.trades) == 0
    assert all(trade.estimated_value_gbp >= Decimal("500") for trade in plan.trades)


def test_limits_sell_orders_to_2():
    snapshot = create_test_snapshot_with_many_overweight()

    plan = generate_trade_plan(snapshot, max_sells=2)
    sell_trades = [trade for trade in plan.trades if trade.action == "SELL"]

    assert len(sell_trades) <= 2


def test_limits_buy_orders_to_3():
    snapshot = create_test_snapshot_with_many_underweight()

    plan = generate_trade_plan(snapshot, max_buys=3)
    buy_trades = [trade for trade in plan.trades if trade.action == "BUY"]

    assert len(buy_trades) <= 3


def test_refuses_buys_exceeding_cash_pool():
    snapshot = create_test_snapshot(
        cash=1000,
        positions=[
            ("VWRP", 0, 100.0, 50.0, 0.0),
            ("SEMI", 0, 100.0, 50.0, 0.0),
        ],
    )

    plan = generate_trade_plan(snapshot)
    total_buy_value = sum(
        trade.estimated_value_gbp for trade in plan.trades if trade.action == "BUY"
    )

    assert total_buy_value <= snapshot.cash_balance_gbp


def test_sell_proceeds_added_to_cash_pool():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("OVER", 150, 40.0, 50.0, 60.0),
            ("UNDER", 100, 40.0, 50.0, 40.0),
        ],
    )

    plan = generate_trade_plan(snapshot)
    buy_value = sum(
        trade.estimated_value_gbp for trade in plan.trades if trade.action == "BUY"
    )
    sell_value = sum(
        trade.estimated_value_gbp for trade in plan.trades if trade.action == "SELL"
    )

    assert buy_value == Decimal("1000.0000000000")
    assert sell_value == Decimal("1000.0000000000")
    assert plan.projected_post_trade_cash == Decimal("0.0000000000")


def test_prioritizes_most_underweight_for_buys():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("UW1", 0, 1.0, 10.0, 0.0),
            ("UW2", 100, 0.1, 10.0, 1.0),
            ("UW3", 200, 0.1, 10.0, 2.0),
            ("UW4", 300, 0.1, 10.0, 3.0),
            ("OVER", 8400, 1.0, 50.0, 84.0),
            ("BAL", 1000, 1.0, 10.0, 10.0),
        ],
    )

    plan = generate_trade_plan(snapshot, max_buys=2)
    buy_tickers = [trade.ticker for trade in plan.trades if trade.action == "BUY"]

    assert buy_tickers == ["UW1", "UW2"]


def test_prioritizes_most_overweight_for_sells():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("OW1", 200, 10.0, 10.0, 20.0),
            ("OW2", 190, 10.0, 10.0, 19.0),
            ("OW3", 180, 10.0, 10.0, 18.0),
            ("OW4", 170, 10.0, 10.0, 17.0),
            ("UW", 160, 10.0, 50.0, 16.0),
            ("BAL", 100, 10.0, 10.0, 10.0),
        ],
    )

    plan = generate_trade_plan(snapshot, max_sells=2)
    sell_tickers = [trade.ticker for trade in plan.trades if trade.action == "SELL"]

    assert sell_tickers == ["OW1", "OW2"]


def test_exact_math_for_sell_quantity():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("OVER", 150, 40.0, 50.0, 60.0),
            ("UNDER", 100, 40.0, 50.0, 40.0),
        ],
    )

    plan = generate_trade_plan(snapshot)
    sell_trade = next(trade for trade in plan.trades if trade.action == "SELL")

    assert sell_trade.quantity == Decimal("25.0000000000")
    assert sell_trade.estimated_value_gbp == Decimal("1000.0000000000")


def test_exact_math_for_buy_quantity():
    snapshot = create_test_snapshot(
        cash=1000,
        positions=[
            ("UNDER", 0, 40.0, 50.0, 0.0),
            ("BAL", 50, 20.0, 50.0, 50.0),
        ],
    )

    plan = generate_trade_plan(snapshot)
    buy_trade = next(trade for trade in plan.trades if trade.action == "BUY")

    assert buy_trade.quantity == Decimal("25.0000000000")
    assert buy_trade.estimated_value_gbp == Decimal("1000.0000000000")


def test_total_value_calculation():
    snapshot = create_test_snapshot(
        cash=250,
        positions=[
            ("VWRP", 100, 10.0, 50.0, 57.1428571429),
            ("SEMI", 25, 20.0, 50.0, 28.5714285714),
        ],
    )

    plan = generate_trade_plan(snapshot)

    assert plan.total_value_before == Decimal("1750.0000000000")
    assert plan.total_value_after == Decimal("1750.0000000000")


def test_no_trade_at_exactly_5_pct_drift_boundary():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("VWRP", 400, 10.0, 35.0, 40.0),
            ("SEMI", 300, 10.0, 35.0, 30.0),
            ("BOND", 300, 10.0, 30.0, 30.0),
        ],
    )

    plan = generate_trade_plan(snapshot)

    assert len(plan.trades) == 0


def test_keeps_trade_at_exactly_500_gbp_boundary():
    snapshot = create_test_snapshot(
        cash=0,
        positions=[
            ("OVER", 3000, 1.0, 50.0, 60.0),
            ("UNDER", 2000, 1.0, 50.0, 40.0),
        ],
    )

    plan = generate_trade_plan(snapshot)

    assert len(plan.trades) == 2
    assert all(trade.estimated_value_gbp == Decimal("500.0000000000") for trade in plan.trades)
