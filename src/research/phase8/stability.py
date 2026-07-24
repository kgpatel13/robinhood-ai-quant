from __future__ import annotations

import json
from typing import cast

import pandas as pd

type ParameterValue = int | float | str | bool | None
type ParameterMap = dict[str, ParameterValue]


def _as_number(value: ParameterValue) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except ValueError:
        return None


def _parameter_distance(left: ParameterMap, right: ParameterMap) -> float:
    shared = sorted(set(left).intersection(right))
    if not shared:
        return float("inf")
    distances: list[float] = []
    for name in shared:
        first = _as_number(left[name])
        second = _as_number(right[name])
        if first is None or second is None:
            distances.append(0.0 if left[name] == right[name] else 1.0)
            continue
        scale = max(abs(first), abs(second), 1.0)
        distances.append(abs(first - second) / scale)
    return sum(distances) / len(distances)


def _load_parameters(value: object) -> ParameterMap:
    loaded = json.loads(str(value))
    if not isinstance(loaded, dict):
        raise ValueError("parameters_json must decode to an object")
    return cast(ParameterMap, loaded)


def apply_neighborhood_stability(
    tournament: pd.DataFrame,
    *,
    score_column: str = "oos_sharpe_ratio",
    tolerance: float = 0.25,
    maximum_distance: float = 0.20,
    minimum_neighbors: int = 1,
) -> pd.DataFrame:
    result = tournament.reset_index(drop=True).copy()
    parameters = [_load_parameters(value) for value in result["parameters_json"]]
    scores = pd.to_numeric(result[score_column], errors="coerce").fillna(0.0).to_numpy()
    values: list[float] = []
    neighbor_counts: list[int] = []
    for index in range(len(result)):
        row = result.iloc[index]
        base_strategy = str(row["base_strategy"])
        neighbors: list[int] = []
        for other_index in range(len(result)):
            if index == other_index:
                continue
            other = result.iloc[other_index]
            if str(other["base_strategy"]) != base_strategy:
                continue
            if str(other["symbol"]) != str(row["symbol"]):
                continue
            if _parameter_distance(parameters[index], parameters[other_index]) <= maximum_distance:
                neighbors.append(other_index)
        neighbor_counts.append(len(neighbors))
        if len(neighbors) < minimum_neighbors:
            values.append(0.0)
            continue
        baseline = float(scores[index])
        stable = sum(abs(float(scores[item]) - baseline) <= tolerance for item in neighbors)
        values.append(stable / len(neighbors))
    result["parameter_stability"] = values
    result["parameter_neighbor_count"] = neighbor_counts
    return result
