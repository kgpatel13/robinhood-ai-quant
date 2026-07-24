from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_feature_snapshot(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"timestamp", "close"}
    if not required.issubset(bars.columns):
        missing = sorted(required.difference(bars.columns))
        raise ValueError(f"bars missing required columns: {missing}")
    frame = bars.sort_values("timestamp").copy()
    close = pd.to_numeric(frame["close"], errors="coerce")
    returns = close.pct_change()
    frame["return_1d"] = returns
    frame["momentum_21d"] = close.pct_change(21)
    frame["momentum_63d"] = close.pct_change(63)
    frame["volatility_21d"] = returns.rolling(21).std(ddof=0) * (252.0**0.5)
    frame["volatility_63d"] = returns.rolling(63).std(ddof=0) * (252.0**0.5)
    frame["trend_50_200"] = close.rolling(50).mean() / close.rolling(200).mean() - 1.0
    frame["drawdown"] = close / close.cummax() - 1.0
    return frame


def write_feature_snapshots(
    data_registry: dict[str, Path], symbols: tuple[str, ...], output: Path
) -> list[str]:
    output.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for symbol in symbols:
        snapshot = build_feature_snapshot(pd.read_parquet(data_registry[symbol]))
        path = output / f"{symbol.replace('/', '-')}.parquet"
        snapshot.to_parquet(path, index=False)
        paths.append(str(path))
    return paths
