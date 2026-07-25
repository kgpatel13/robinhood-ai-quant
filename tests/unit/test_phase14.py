from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research.phase14.engine import infer_asset_class, run_phase14
from src.research.phase14.models import Phase14Config


def test_asset_class_inference() -> None:
    assert infer_asset_class("BTC-USD") == "crypto"
    assert infer_asset_class("SPY") == "etf"
    assert infer_asset_class("AAPL") == "stock"
    assert infer_asset_class("AAPL", "equity") == "equity"


def test_phase14_pipeline(tmp_path: Path) -> None:
    timestamps = pd.date_range("2024-01-01", periods=12, freq="30D", tz="UTC")
    trades = pd.DataFrame(
        {
            "symbol": ["AAPL", "BTC-USD"] * 6,
            "asset_class": ["unknown"] * 12,
            "entry_timestamp": timestamps,
            "exit_timestamp": timestamps + pd.Timedelta(days=5),
            "net_return": [0.02, -0.01, 0.03, 0.01] * 3,
            "pnl": [20.0, -10.0, 30.0, 10.0] * 3,
        }
    )
    equity = pd.DataFrame(
        {"timestamp": timestamps, "capital": [10000.0 + i * 50.0 for i in range(12)]}
    )
    rejected = pd.DataFrame({"reason": ["position_limit", "symbol_overlap"]})
    trades_path = tmp_path / "trades.csv"
    equity_path = tmp_path / "equity.csv"
    rejected_path = tmp_path / "rejected.csv"
    trades.to_csv(trades_path, index=False)
    equity.to_csv(equity_path, index=False)
    rejected.to_csv(rejected_path, index=False)
    result = run_phase14(
        Phase14Config(
            executed_trades_path=trades_path,
            rejected_signals_path=rejected_path,
            equity_curve_path=equity_path,
            output_root=tmp_path / "out",
            minimum_total_trades=1,
            minimum_trades_per_group=1,
        )
    )
    assert result.diagnostics_passed
    assert not result.approved_for_phase15_review
    assert (tmp_path / "out" / "asset_class_attribution.csv").exists()
    assert (tmp_path / "out" / "phase14_dashboard.json").exists()
