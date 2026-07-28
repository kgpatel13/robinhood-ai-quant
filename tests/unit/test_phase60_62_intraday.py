from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from src.backtest.intraday import IntradayBacktestEngine
from src.data.intraday import IntradayBarConfig, validate_intraday_bars
from src.execution.intraday import IntradayAction, IntradayPaperOrchestrator
from src.strategies.intraday import IntradayMomentumStrategy, IntradaySignal


def _bars(rows: int = 40) -> pd.DataFrame:
    index = pd.date_range("2026-07-27 13:30", periods=rows, freq="5min", tz="UTC")
    close = [100 + index * 0.15 for index in range(rows)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [value + 0.2 for value in close],
            "low": [value - 0.2 for value in close],
            "close": close,
            "volume": [1_000.0 + index * 20 for index in range(rows)],
        },
        index=index,
    )


def test_intraday_quality_accepts_valid_bars() -> None:
    report = validate_intraday_bars(_bars(), IntradayBarConfig())
    assert report.valid
    assert report.invalid_price_rows == 0


def test_intraday_strategy_detects_positive_momentum() -> None:
    assessment = IntradayMomentumStrategy().assess(_bars())
    assert assessment.signal is IntradaySignal.LONG
    assert assessment.score > 0


def test_intraday_backtest_flattens_positions() -> None:
    result = IntradayBacktestEngine().run(_bars())
    assert result.trade_count >= 1
    assert result.forced_liquidations >= 1
    assert result.final_equity > 0


def test_orchestrator_is_paper_only_and_enters_during_session() -> None:
    orchestrator = IntradayPaperOrchestrator(lambda _: {"AAPL": _bars()})
    moment = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    decisions = orchestrator.evaluate(moment)
    assert decisions[0].action is IntradayAction.ENTER


def test_orchestrator_forces_end_of_day_flattening() -> None:
    orchestrator = IntradayPaperOrchestrator(lambda _: {"AAPL": _bars()})
    moment = datetime(2026, 7, 27, 19, 56, tzinfo=UTC)
    decisions = orchestrator.evaluate(moment, frozenset({"AAPL"}))
    assert decisions[0].action is IntradayAction.FLATTEN
