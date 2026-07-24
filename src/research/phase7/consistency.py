from __future__ import annotations

import pandas as pd


def add_cross_asset_consistency(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    positive_mask = result["oos_excess_cagr"].astype(float) > 0.0
    positive = result.assign(_positive=positive_mask.astype(float))
    mapping = positive.groupby("strategy")["_positive"].mean().to_dict()
    result["cross_asset_consistency"] = result["strategy"].map(mapping).fillna(0.0)
    return result
