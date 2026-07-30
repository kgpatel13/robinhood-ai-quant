from __future__ import annotations

import numpy as np
import pandas as pd

from src.feature_store.indicators import atr, macd, rsi
from src.feature_store.models import FeatureBuildConfig, FeatureMetadata


class MarketFeatureBuilder:
    def __init__(
        self,
        config: FeatureBuildConfig | None = None,
        metadata: FeatureMetadata | None = None,
    ) -> None:
        self.config = config or FeatureBuildConfig()
        self.metadata = metadata or FeatureMetadata("market_features", "1")

    def build(self, frame: pd.DataFrame) -> pd.DataFrame:
        required = {
            self.config.price_column,
            self.config.high_column,
            self.config.low_column,
            self.config.volume_column,
        }
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"missing market columns: {missing}")
        output = frame.copy()
        close = pd.to_numeric(output[self.config.price_column], errors="coerce")
        high = pd.to_numeric(output[self.config.high_column], errors="coerce")
        low = pd.to_numeric(output[self.config.low_column], errors="coerce")
        volume = pd.to_numeric(output[self.config.volume_column], errors="coerce")
        for window in self.config.return_windows:
            output[f"return_{window}"] = close.pct_change(window)
        output["rolling_volatility"] = (
            close.pct_change()
            .rolling(
                self.config.volatility_window,
                min_periods=self.config.volatility_window,
            )
            .std()
        )
        output["momentum"] = close / close.shift(self.config.momentum_window) - 1.0
        output["mean_reversion"] = (
            close
            / close.rolling(
                self.config.momentum_window,
                min_periods=self.config.momentum_window,
            ).mean()
            - 1.0
        )
        output["rsi"] = rsi(close, self.config.rsi_window)
        output["atr"] = atr(high, low, close, self.config.rsi_window)
        macd_line, macd_signal = macd(close)
        output["macd"] = macd_line
        output["macd_signal"] = macd_signal
        average_volume = volume.rolling(20, min_periods=20).mean()
        output["relative_volume"] = volume / average_volume.replace(0.0, np.nan)
        output.attrs["feature_set"] = self.metadata.identifier
        return output

    @staticmethod
    def clean(frame: pd.DataFrame, *, fill_value: float = 0.0) -> pd.DataFrame:
        numeric = frame.select_dtypes(include=["number"]).replace([np.inf, -np.inf], np.nan)
        return numeric.fillna(fill_value)
