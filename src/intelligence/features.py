from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_REQUIRED_COLUMNS = frozenset({"open", "high", "low", "close", "volume"})


@dataclass(frozen=True)
class FeatureConfig:
    return_windows: tuple[int, ...] = (1, 5, 10, 20)
    volatility_windows: tuple[int, ...] = (10, 20)
    trend_windows: tuple[int, ...] = (10, 20, 50)
    rsi_window: int = 14
    atr_window: int = 14
    volume_window: int = 20

    def __post_init__(self) -> None:
        if any(window < 1 for window in self.return_windows):
            raise ValueError("return windows must be positive")
        other_windows = (
            *self.volatility_windows,
            *self.trend_windows,
            self.rsi_window,
            self.atr_window,
            self.volume_window,
        )
        if any(window < 2 for window in other_windows):
            raise ValueError("rolling feature windows must be at least two")


class TechnicalFeatureEngineer:
    """Build deterministic, leakage-safe technical features from OHLCV bars."""

    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config or FeatureConfig()

    def transform(self, bars: pd.DataFrame) -> pd.DataFrame:
        missing = _REQUIRED_COLUMNS - set(bars.columns)
        if missing:
            raise ValueError(f"bars are missing required columns: {sorted(missing)}")
        frame = bars.copy()
        for column in _REQUIRED_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.replace([np.inf, -np.inf], np.nan)
        close = frame["close"]
        returns = close.pct_change()

        features = pd.DataFrame(index=frame.index)
        for window in self.config.return_windows:
            features[f"return_{window}"] = close.pct_change(window)
        for window in self.config.volatility_windows:
            features[f"volatility_{window}"] = returns.rolling(window).std(ddof=0)
        for window in self.config.trend_windows:
            average = close.rolling(window).mean()
            features[f"trend_distance_{window}"] = close / average - 1.0

        features["rsi"] = self._rsi(close, self.config.rsi_window) / 100.0
        features["atr_pct"] = self._atr(frame, self.config.atr_window) / close.replace(0.0, np.nan)
        average_volume = frame["volume"].rolling(self.config.volume_window).mean()
        features["relative_volume"] = frame["volume"] / average_volume.replace(0.0, np.nan)
        features["intraday_range"] = (frame["high"] - frame["low"]) / close.replace(0.0, np.nan)
        features["close_location"] = (close - frame["low"]) / (
            frame["high"] - frame["low"]
        ).replace(0.0, np.nan)
        return features.replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def feature_names(config: FeatureConfig | None = None) -> tuple[str, ...]:
        selected = config or FeatureConfig()
        names = [f"return_{window}" for window in selected.return_windows]
        names.extend(f"volatility_{window}" for window in selected.volatility_windows)
        names.extend(f"trend_distance_{window}" for window in selected.trend_windows)
        names.extend(("rsi", "atr_pct", "relative_volume", "intraday_range", "close_location"))
        return tuple(names)

    @staticmethod
    def _rsi(close: pd.Series, window: int) -> pd.Series:
        delta = close.diff()
        gains = delta.clip(lower=0.0).rolling(window).mean()
        losses = -delta.clip(upper=0.0).rolling(window).mean()
        relative_strength = gains / losses.replace(0.0, np.nan)
        return 100.0 - 100.0 / (1.0 + relative_strength)

    @staticmethod
    def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
        previous_close = frame["close"].shift(1)
        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - previous_close).abs(),
                (frame["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.rolling(window).mean()
