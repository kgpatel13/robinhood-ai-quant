from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.execution import (
    AccountSnapshot,
    OrderRequest,
    OrderSide,
    Position,
    PreTradeRiskConfig,
    PreTradeRiskEngine,
    RiskDecisionType,
    RiskReason,
)


def _account(*, cash: float = 10_000.0, positions: tuple[Position, ...] = ()) -> AccountSnapshot:
    equity = cash + sum(position.market_value for position in positions)
    return AccountSnapshot(cash, equity, cash, positions, datetime.now(UTC))


def test_approves_order_within_all_limits() -> None:
    engine = PreTradeRiskEngine(
        PreTradeRiskConfig(max_position_weight=0.50, max_order_notional=5_000)
    )
    order = OrderRequest("AAPL", 20, OrderSide.BUY)

    evaluation = engine.evaluate((order,), _account(), {"AAPL": 100.0})

    decision = evaluation.decisions[0]
    assert decision.decision is RiskDecisionType.APPROVE
    assert decision.reason is RiskReason.APPROVED
    assert decision.approved_order == order


def test_resizes_order_to_maximum_position_weight() -> None:
    engine = PreTradeRiskEngine(
        PreTradeRiskConfig(max_position_weight=0.20, max_order_notional=10_000)
    )
    order = OrderRequest("AAPL", 50, OrderSide.BUY)

    evaluation = engine.evaluate((order,), _account(), {"AAPL": 100.0})

    decision = evaluation.decisions[0]
    assert decision.decision is RiskDecisionType.RESIZE
    assert decision.reason is RiskReason.POSITION_WEIGHT_LIMIT
    assert decision.approved_order is not None
    assert decision.approved_order.quantity == pytest.approx(20)


def test_resizes_buy_to_preserve_cash_reserve() -> None:
    engine = PreTradeRiskEngine(
        PreTradeRiskConfig(
            max_position_weight=0.80,
            max_order_notional=20_000,
            max_gross_exposure=0.80,
            min_cash_reserve=0.20,
        )
    )
    order = OrderRequest("AAPL", 100, OrderSide.BUY)

    decision = engine.evaluate((order,), _account(), {"AAPL": 100.0}).decisions[0]

    assert decision.decision is RiskDecisionType.RESIZE
    assert decision.approved_notional == pytest.approx(8_000)


def test_rejects_new_symbol_when_position_count_is_full() -> None:
    position = Position("MSFT", 10, 100, 100)
    engine = PreTradeRiskEngine(PreTradeRiskConfig(max_open_positions=1))
    order = OrderRequest("AAPL", 1, OrderSide.BUY)

    decision = engine.evaluate(
        (order,), _account(cash=9_000, positions=(position,)), {"AAPL": 100.0}
    ).decisions[0]

    assert decision.decision is RiskDecisionType.REJECT
    assert decision.reason is RiskReason.OPEN_POSITION_LIMIT


def test_sell_is_resized_to_available_position() -> None:
    position = Position("AAPL", 5, 100, 100)
    engine = PreTradeRiskEngine()
    order = OrderRequest("AAPL", 10, OrderSide.SELL)

    decision = engine.evaluate(
        (order,), _account(cash=9_500, positions=(position,)), {"AAPL": 100.0}
    ).decisions[0]

    assert decision.decision is RiskDecisionType.RESIZE
    assert decision.reason is RiskReason.INSUFFICIENT_POSITION
    assert decision.approved_order is not None
    assert decision.approved_order.quantity == 5


def test_sell_releases_cash_for_following_buy() -> None:
    position = Position("MSFT", 50, 100, 100)
    engine = PreTradeRiskEngine(
        PreTradeRiskConfig(
            max_position_weight=0.50,
            max_order_notional=5_000,
            max_gross_exposure=0.95,
            min_cash_reserve=0.05,
        )
    )
    orders = (
        OrderRequest("MSFT", 50, OrderSide.SELL),
        OrderRequest("AAPL", 50, OrderSide.BUY),
    )

    evaluation = engine.evaluate(
        orders,
        _account(cash=5_000, positions=(position,)),
        {"MSFT": 100.0, "AAPL": 100.0},
    )

    assert evaluation.rejected_count == 0
    assert evaluation.approved_orders == orders


def test_invalid_price_is_rejected() -> None:
    order = OrderRequest("AAPL", 1, OrderSide.BUY)

    decision = PreTradeRiskEngine().evaluate((order,), _account(), {}).decisions[0]

    assert decision.decision is RiskDecisionType.REJECT
    assert decision.reason is RiskReason.INVALID_PRICE
