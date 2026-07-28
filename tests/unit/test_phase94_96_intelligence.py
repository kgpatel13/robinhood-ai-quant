from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.intelligence import (
    AssistantContext,
    AtlasAssistant,
    ExplanationJournal,
    MultiTimeframeAnalyzer,
    TimeframeConfig,
    TradeExplanationBuilder,
)


def bars(slope: float, length: int = 120) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=length, freq="D")
    close = 100.0 + np.arange(length) * slope
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(length, 1000.0),
        },
        index=index,
    )


def test_multitimeframe_alignment_allows_trade() -> None:
    frames = {name: bars(0.3) for name in ("monthly", "weekly", "daily", "hourly", "intraday")}
    result = MultiTimeframeAnalyzer().assess("SPY", frames)
    assert result.aggregate_score > 0
    assert result.confirmation_score == 1.0
    assert result.trading_allowed


def test_multitimeframe_conflict_reduces_quality() -> None:
    frames = {
        "monthly": bars(0.3),
        "weekly": bars(0.3),
        "daily": bars(-0.3),
        "hourly": bars(-0.3),
        "intraday": bars(-0.3),
    }
    result = MultiTimeframeAnalyzer(TimeframeConfig(conflict_penalty=0.5)).assess("QQQ", frames)
    assert result.conflict_score > 0
    assert result.confirmation_score < 1


def test_explanation_journal_round_trip(tmp_path: Path) -> None:
    frames = {name: bars(0.3) for name in ("monthly", "weekly", "daily", "hourly", "intraday")}
    assessment = MultiTimeframeAnalyzer().assess("AAPL", frames)
    explanation = TradeExplanationBuilder().build(
        assessment,
        regime="orderly_uptrend",
        model_probability=0.72,
        risk_reward_ratio=2.4,
    )
    journal = ExplanationJournal(tmp_path / "explanations.jsonl")
    journal.append(explanation)
    loaded = journal.load()
    assert loaded[-1]["symbol"] == "AAPL"
    assert loaded[-1]["action"] == "BUY"


def test_assistant_answers_deterministically() -> None:
    context = AssistantContext(
        positions=(
            {"symbol": "AAPL", "quantity": 5, "unrealized_pnl": -42.0},
            {"symbol": "MSFT", "quantity": 2, "unrealized_pnl": 15.0},
        ),
        performance={"total_return": "4.2%", "sharpe": 1.1},
    )
    assistant = AtlasAssistant()
    losers = assistant.answer("Show losing positions", context)
    performance = assistant.answer("What is performance?", context)
    assert losers.evidence_count == 1
    assert "AAPL" in losers.answer
    assert performance.intent == "performance"
