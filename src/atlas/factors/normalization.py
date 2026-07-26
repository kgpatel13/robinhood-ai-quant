from __future__ import annotations

import math
from collections.abc import Mapping


def winsorize(
    values: Mapping[str, float | None],
    lower: float = 0.025,
    upper: float = 0.975,
) -> dict[str, float | None]:
    if not 0.0 <= lower < upper <= 1.0:
        raise ValueError("Winsorization bounds must satisfy 0 <= lower < upper <= 1")
    finite = sorted(
        value for value in values.values() if value is not None and math.isfinite(value)
    )
    if not finite:
        return dict(values)
    low = _quantile(finite, lower)
    high = _quantile(finite, upper)
    return {
        key: None if value is None or not math.isfinite(value) else min(max(value, low), high)
        for key, value in values.items()
    }


def zscore(values: Mapping[str, float | None]) -> dict[str, float | None]:
    finite = [value for value in values.values() if value is not None and math.isfinite(value)]
    if not finite:
        return {key: None for key in values}
    average = sum(finite) / len(finite)
    variance = sum((value - average) ** 2 for value in finite) / len(finite)
    deviation = math.sqrt(variance)
    if deviation == 0.0:
        return {
            key: (0.0 if value is not None and math.isfinite(value) else None)
            for key, value in values.items()
        }
    return {
        key: None if value is None or not math.isfinite(value) else (value - average) / deviation
        for key, value in values.items()
    }


def percentile_rank(values: Mapping[str, float | None]) -> dict[str, float | None]:
    finite_items = sorted(
        (
            (key, value)
            for key, value in values.items()
            if value is not None and math.isfinite(value)
        ),
        key=lambda item: (item[1], item[0]),
    )
    output: dict[str, float | None] = {key: None for key in values}
    count = len(finite_items)
    if count == 0:
        return output
    if count == 1:
        output[finite_items[0][0]] = 0.5
        return output
    index = 0
    while index < count:
        end = index + 1
        while end < count and finite_items[end][1] == finite_items[index][1]:
            end += 1
        average_rank = (index + end - 1) / 2.0
        percentile = average_rank / (count - 1)
        for position in range(index, end):
            output[finite_items[position][0]] = percentile
        index = end
    return output


def _quantile(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = probability * (len(sorted_values) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    fraction = position - lower_index
    return sorted_values[lower_index] * (1.0 - fraction) + sorted_values[upper_index] * fraction
