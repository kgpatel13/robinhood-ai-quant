from __future__ import annotations

import pandas as pd

from src.research.phase11.dataset import KEY_COLUMNS, LABEL_COLUMNS
from src.research.phase11.features import FEATURE_COLUMNS


def audit_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            [{"check": "dataset_not_empty", "passed": False, "violations": 1, "detail": "No rows"}]
        )
    signal = pd.to_datetime(dataset["timestamp"], utc=True)
    entry = pd.to_datetime(dataset["entry_timestamp"], utc=True)
    exit_time = pd.to_datetime(dataset["exit_timestamp"], utc=True)
    checks = [
        _check("dataset_not_empty", True, 0, f"{len(dataset)} rows"),
        _check(
            "unique_observation_keys",
            not dataset.duplicated(list(KEY_COLUMNS)).any(),
            int(dataset.duplicated(list(KEY_COLUMNS)).sum()),
            "timestamp/symbol/asset_class/horizon",
        ),
        _check(
            "entry_after_signal",
            bool((entry > signal).all()),
            int((entry <= signal).sum()),
            "Features are known before entry",
        ),
        _check(
            "exit_after_entry",
            bool((exit_time >= entry).all()),
            int((exit_time < entry).sum()),
            "Labels use future bars only",
        ),
        _check(
            "feature_completeness",
            not dataset[list(FEATURE_COLUMNS)].isna().any().any(),
            int(dataset[list(FEATURE_COLUMNS)].isna().sum().sum()),
            "No missing engineered features",
        ),
        _check(
            "label_completeness",
            not dataset[list(LABEL_COLUMNS)].isna().any().any(),
            int(dataset[list(LABEL_COLUMNS)].isna().sum().sum()),
            "No missing labels",
        ),
        _check(
            "finite_prices",
            bool((dataset[["signal_close", "entry_price", "exit_price"]] > 0).all().all()),
            int((dataset[["signal_close", "entry_price", "exit_price"]] <= 0).sum().sum()),
            "Prices must be positive",
        ),
    ]
    return pd.DataFrame(checks)


def _check(check: str, passed: bool, violations: int, detail: str) -> dict[str, object]:
    return {"check": check, "passed": passed, "violations": violations, "detail": detail}
