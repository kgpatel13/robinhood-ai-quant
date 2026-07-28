from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from src.execution import (
    AccountProtectionConfig,
    AccountProtectionEngine,
    AccountProtectionState,
    AccountProtectionStore,
    AccountSnapshot,
    ExecutionJournal,
    OrderRequest,
    OrderSide,
    Position,
    ProtectionReason,
    ProtectionStatus,
    ShortSwingConfig,
    ShortSwingLifecycle,
    ShortSwingTargetProvider,
    SwingExitReason,
    SwingPositionState,
    SwingPositionStore,
)
from src.strategies.short_swing import ShortSwingEnsemble, ShortSwingEnsembleConfig


def _account(equity: float, *, position: Position | None = None) -> AccountSnapshot:
    positions = () if position is None else (position,)
    cash = equity - sum(item.market_value for item in positions)
    return AccountSnapshot(cash, equity, cash, positions, datetime.now(UTC))


def test_account_protection_allows_healthy_account() -> None:
    state = AccountProtectionState(date(2026, 7, 27), 10_000, 10_000, 10_500)
    decision = AccountProtectionEngine().evaluate(_account(10_200), state)

    assert decision.status is ProtectionStatus.ACTIVE
    assert decision.reason is ProtectionReason.CLEAR
    assert decision.trading_allowed


def test_account_protection_pauses_on_daily_loss() -> None:
    state = AccountProtectionState(date(2026, 7, 27), 10_000, 10_000, 10_000)
    engine = AccountProtectionEngine(AccountProtectionConfig(max_daily_loss=0.03))

    decision = engine.evaluate(_account(9_600), state)

    assert decision.status is ProtectionStatus.PAUSED
    assert decision.reason is ProtectionReason.DAILY_LOSS_LIMIT
    assert not decision.trading_allowed


def test_account_protection_locks_on_drawdown() -> None:
    state = AccountProtectionState(date(2026, 7, 27), 9_000, 9_500, 12_000)
    engine = AccountProtectionEngine(AccountProtectionConfig(max_drawdown=0.15))

    decision = engine.evaluate(_account(9_500), state)

    assert decision.status is ProtectionStatus.LOCKED
    assert decision.reason is ProtectionReason.DRAWDOWN_LIMIT


def test_short_swing_exits_at_maximum_holding_period() -> None:
    position = Position("AAPL", 10, 100, 103)
    account = _account(10_000, position=position)
    states = {"AAPL": SwingPositionState("AAPL", date(2026, 7, 20), 100, 105)}

    exits = ShortSwingLifecycle(ShortSwingConfig(max_holding_days=5)).evaluate_exits(
        account, states, {"AAPL": 103}, date(2026, 7, 27)
    )

    assert len(exits) == 1
    assert exits[0].reason is SwingExitReason.MAX_HOLD
    assert exits[0].order.side is OrderSide.SELL
    assert exits[0].order.quantity == 10


def test_short_swing_stop_loss_and_profit_target() -> None:
    lifecycle = ShortSwingLifecycle(ShortSwingConfig(stop_loss=0.05, profit_target=0.10))
    state = SwingPositionState("AAPL", date(2026, 7, 26), 100, 112)
    position = Position("AAPL", 5, 100, 94)

    stop = lifecycle.evaluate_exits(
        _account(10_000, position=position), {"AAPL": state}, {"AAPL": 94}, date(2026, 7, 27)
    )
    profit = lifecycle.evaluate_exits(
        _account(10_000, position=position), {"AAPL": state}, {"AAPL": 111}, date(2026, 7, 27)
    )

    assert stop[0].reason is SwingExitReason.STOP_LOSS
    assert profit[0].reason is SwingExitReason.PROFIT_TARGET


def _bars(values: list[float]) -> pd.DataFrame:
    close = pd.Series(values, dtype=float)
    return pd.DataFrame({"close": close, "high": close * 1.002, "low": close * 0.998})


def test_short_swing_ensemble_ranks_and_caps_positions() -> None:
    ensemble = ShortSwingEnsemble(
        ShortSwingEnsembleConfig(
            lookback=5,
            breakout_window=3,
            pullback_window=3,
            max_positions=2,
            min_score=0.45,
            cash_reserve=0.10,
        )
    )
    bars = {
        "AAPL": _bars([100, 101, 102, 103, 104, 106, 108]),
        "MSFT": _bars([100, 100, 101, 101, 102, 103, 104]),
        "FLAT": _bars([100, 100, 100, 100, 100, 100, 100]),
    }

    ranked = ensemble.rank(bars)
    weights = ensemble.target_weights(bars)

    assert ranked[0].symbol == "AAPL"
    assert len(weights) <= 2
    assert sum(weights.values()) == pytest.approx(0.90)
    assert all(weight > 0 for weight in weights.values())


def test_short_swing_ensemble_returns_cash_when_no_candidate_qualifies() -> None:
    ensemble = ShortSwingEnsemble(
        ShortSwingEnsembleConfig(
            lookback=5,
            breakout_window=3,
            pullback_window=3,
            min_score=0.99,
        )
    )

    assert ensemble.target_weights({"AAPL": _bars([100, 99, 98, 97, 96, 95, 94])}) == {}


def test_protection_and_swing_states_round_trip(tmp_path: Path) -> None:
    journal = ExecutionJournal(tmp_path / "execution.sqlite")
    protection_state = AccountProtectionState(date(2026, 7, 27), 10_000, 9_900, 10_500, 2)
    AccountProtectionStore(journal).save(protection_state)
    swing_states = {"AAPL": SwingPositionState("AAPL", date(2026, 7, 25), 100, 105)}
    SwingPositionStore(journal).save(swing_states)

    assert AccountProtectionStore(journal).load() == protection_state
    assert SwingPositionStore(journal).load() == swing_states


def test_short_swing_filters_daily_trades_and_position_slots() -> None:
    lifecycle = ShortSwingLifecycle(
        ShortSwingConfig(max_trades_per_day=2, max_simultaneous_positions=2)
    )
    account = _account(10_000, position=Position("MSFT", 1, 100, 100))
    orders = (
        OrderRequest("AAPL", 1, OrderSide.BUY),
        OrderRequest("NVDA", 1, OrderSide.BUY),
        OrderRequest("QQQ", 1, OrderSide.BUY),
        OrderRequest("MSFT", 1, OrderSide.SELL),
    )

    filtered = lifecycle.filter_entry_orders(orders, account)

    assert [order.symbol for order in filtered] == ["AAPL", "MSFT"]


def test_short_swing_target_provider_integrates_with_orchestration_contract() -> None:
    bars = {"AAPL": _bars([100, 101, 102, 103, 104, 106, 108])}
    ensemble = ShortSwingEnsemble(
        ShortSwingEnsembleConfig(
            lookback=5,
            breakout_window=3,
            pullback_window=3,
            min_score=0.40,
        )
    )
    provider = ShortSwingTargetProvider(lambda _as_of: bars, ensemble)

    target = provider.generate(datetime.now(UTC), _account(10_000))

    assert target.model_name == "short-swing-ensemble-v1"
    assert "AAPL" in target.weights
