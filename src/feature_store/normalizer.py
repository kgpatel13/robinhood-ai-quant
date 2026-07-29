from __future__ import annotations

import pandas as pd
from sklearn.preprocessing import StandardScaler


class FeatureNormalizer:
    def __init__(self) -> None:
        self._scaler = StandardScaler()
        self._columns: tuple[str, ...] = ()

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        self._columns = tuple(frame.columns)
        values = self._scaler.fit_transform(frame)
        return pd.DataFrame(values, index=frame.index, columns=self._columns)

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self._columns:
            raise RuntimeError("normalizer has not been fitted")
        if tuple(frame.columns) != self._columns:
            raise ValueError("feature columns do not match fitted columns")
        values = self._scaler.transform(frame)
        return pd.DataFrame(values, index=frame.index, columns=self._columns)
