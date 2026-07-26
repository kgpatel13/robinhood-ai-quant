from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class FactorStatistics:
    count: int
    coverage: float
    minimum: float | None
    maximum: float | None
    mean: float | None
    median: float | None
    standard_deviation: float | None


def factor_statistics(
    scores: Mapping[str, Mapping[str, float | None]],
) -> dict[str, FactorStatistics]:
    factors = sorted({factor for row in scores.values() for factor in row})
    total_assets = len(scores)
    output: dict[str, FactorStatistics] = {}
    for factor in factors:
        values = [row[factor] for row in scores.values() if row.get(factor) is not None]
        finite = [float(value) for value in values if value is not None and math.isfinite(value)]
        if not finite:
            output[factor] = FactorStatistics(0, 0.0, None, None, None, None, None)
            continue
        average = sum(finite) / len(finite)
        variance = sum((value - average) ** 2 for value in finite) / len(finite)
        output[factor] = FactorStatistics(
            count=len(finite),
            coverage=len(finite) / total_assets if total_assets else 0.0,
            minimum=min(finite),
            maximum=max(finite),
            mean=average,
            median=median(finite),
            standard_deviation=math.sqrt(variance),
        )
    return output


def factor_correlations(
    scores: Mapping[str, Mapping[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    factors = sorted({factor for row in scores.values() for factor in row})
    return {
        left: {right: _pairwise_correlation(scores, left, right) for right in factors}
        for left in factors
    }


def _pairwise_correlation(
    scores: Mapping[str, Mapping[str, float | None]], left: str, right: str
) -> float | None:
    pairs = [
        (row[left], row[right])
        for row in scores.values()
        if row.get(left) is not None and row.get(right) is not None
    ]
    finite = [
        (float(x), float(y))
        for x, y in pairs
        if x is not None and y is not None and math.isfinite(x) and math.isfinite(y)
    ]
    if len(finite) < 2:
        return None
    xs = [item[0] for item in finite]
    ys = [item[1] for item in finite]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in finite)
    x_sum = sum((x - x_mean) ** 2 for x in xs)
    y_sum = sum((y - y_mean) ** 2 for y in ys)
    denominator = math.sqrt(x_sum * y_sum)
    return None if denominator == 0.0 else numerator / denominator
