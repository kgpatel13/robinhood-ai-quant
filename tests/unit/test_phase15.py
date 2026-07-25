from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.research.phase15.engine import run_phase15
from src.research.phase15.models import Phase15Config


def test_phase15_pipeline(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    rows = 900
    probability = rng.uniform(0.45, 0.75, rows)
    returns = (probability - 0.56) * 0.12 + rng.normal(0.0, 0.02, rows)
    frame = pd.DataFrame(
        {
            "holding_period": np.where(np.arange(rows) % 2 == 0, 10, 20),
            "fold": np.arange(rows) % 5 + 1,
            "timestamp": pd.date_range("2015-01-01", periods=rows, freq="D", tz="UTC"),
            "symbol": np.where(np.arange(rows) % 3 == 0, "BTC-USD", "AAPL"),
            "probability": probability,
            "gross_return": returns + 0.001,
            "net_return_after_costs": returns,
        }
    )
    path = tmp_path / "trades.csv"
    frame.to_csv(path, index=False)
    result = run_phase15(
        Phase15Config(
            trades_path=path,
            output_root=tmp_path / "out",
            folds=3,
            minimum_train_rows=200,
            minimum_test_trades=5,
            minimum_auc=0.45,
            minimum_profit_factor=0.8,
        )
    )
    assert result.diagnostics_passed
    assert result.folds_completed == 3
    assert (tmp_path / "out" / "phase15_dashboard.json").exists()
    assert (tmp_path / "out" / "phase15_champion.joblib").exists()
    assert (tmp_path / "out" / "feature_importance.csv").exists()
