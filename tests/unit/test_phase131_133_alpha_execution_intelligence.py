from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from src.alpha_engine import AlphaEngine, AlphaHorizon
from src.microstructure import (
    MarketQualityDecision,
    MicrostructureEvaluator,
    MicrostructureSnapshot,
    default_policy,
)
from src.paper_analytics import PaperAnalyticsTracker, PaperEventType, PaperTradeEvent
from src.research_journal import ResearchEntry, ResearchJournal


def _market() -> pd.DataFrame:
    close = np.linspace(100.0, 120.0, 80)
    volume = np.full(80, 1_000_000.0)
    volume[-1] = 1_800_000.0
    return pd.DataFrame({"close": close, "volume": volume})


def test_alpha_engine_produces_explainable_signal() -> None:
    signal = AlphaEngine().evaluate(symbol="aapl", market=_market(), horizon=AlphaHorizon.SWING)
    assert signal.symbol == "AAPL"
    assert -1.0 <= signal.score <= 1.0
    assert len(signal.factors) == 5
    assert sum(factor.attribution for factor in signal.factors) != 0


def test_cross_sectional_rank_is_bounded() -> None:
    engine = AlphaEngine()
    first = engine.evaluate(symbol="AAA", market=_market(), horizon=AlphaHorizon.WEEKLY)
    declining = _market().copy()
    declining["close"] = declining["close"].iloc[::-1].to_numpy()
    second = engine.evaluate(symbol="BBB", market=declining, horizon=AlphaHorizon.WEEKLY)
    ranks = engine.cross_sectional_rank((first, second))
    assert ranks["AAA"] == 1.0
    assert ranks["BBB"] == -1.0


def test_microstructure_rejects_poor_market_quality() -> None:
    evaluator = MicrostructureEvaluator(default_policy("scalping"))
    report = evaluator.evaluate(
        MicrostructureSnapshot(99.0, 101.0, 100.0, 10_000.0, 100.0, 250_000.0, 0.05, 1)
    )
    assert report.decision is MarketQualityDecision.REJECT
    assert report.size_multiplier == 0.0
    assert report.reasons


def test_microstructure_approves_liquid_market() -> None:
    evaluator = MicrostructureEvaluator(default_policy("day_trading"))
    report = evaluator.evaluate(
        MicrostructureSnapshot(99.99, 100.01, 100.0, 5_000_000.0, 1_000_000.0, 10_000.0, 0.002, 60)
    )
    assert report.decision is MarketQualityDecision.APPROVE
    assert report.size_multiplier == 1.0


def test_paper_analytics_tracks_fill_and_pnl() -> None:
    tracker = PaperAnalyticsTracker()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    tracker.record(PaperTradeEvent("t1", PaperEventType.SIGNAL, base, "AAPL", "swing"))
    tracker.record(
        PaperTradeEvent(
            "t1", PaperEventType.ORDER, base + timedelta(seconds=1), "AAPL", "swing", 10
        )
    )
    tracker.record(
        PaperTradeEvent(
            "t1",
            PaperEventType.FILL,
            base + timedelta(seconds=2),
            "AAPL",
            "swing",
            10,
            100.1,
            100.0,
        )
    )
    tracker.record(
        PaperTradeEvent(
            "t1", PaperEventType.CLOSE, base + timedelta(days=1), "AAPL", "swing", 10, pnl=25.0
        )
    )
    report = tracker.report(strategy="swing")
    assert report.fill_ratio == 1.0
    assert report.win_rate == 1.0
    assert report.total_pnl == 25.0
    assert report.average_slippage_bps > 0


def test_research_journal_round_trip(tmp_path) -> None:
    journal = ResearchJournal(tmp_path / "journal.jsonl")
    entry = ResearchEntry(
        "exp-1", "strategy-1", "model-1", "features-v1", "bull", {"sharpe": 1.2}, "paper"
    )
    journal.append(entry)
    loaded = journal.latest()
    assert loaded is not None
    assert loaded.experiment_id == "exp-1"
    assert loaded.metrics["sharpe"] == 1.2
