from __future__ import annotations

from collections import Counter

from src.research.models import OptimizationResult


def parameter_stability(result: OptimizationResult, top_fraction: float = 0.20) -> float:
    if not result.trials:
        return 0.0
    count = max(1, round(len(result.trials) * top_fraction))
    top = result.trials[:count]
    scores: list[float] = []
    names = sorted(top[0].parameters)
    for name in names:
        values = [trial.parameters[name] for trial in top]
        frequency = Counter(values).most_common(1)[0][1]
        scores.append(frequency / len(values))
    return float(sum(scores) / len(scores)) if scores else 0.0
