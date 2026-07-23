from __future__ import annotations

import itertools
import random

from src.research.models import OptimizationConfig


def generate_candidates(config: OptimizationConfig) -> list[dict[str, int | float]]:
    names = [item.name for item in config.parameters]
    combinations = [
        dict(zip(names, values, strict=True))
        for values in itertools.product(*(item.values for item in config.parameters))
    ]
    if config.method == "grid":
        if config.max_evaluations is not None:
            return combinations[: config.max_evaluations]
        return combinations
    rng = random.Random(config.seed)
    rng.shuffle(combinations)
    limit = config.max_evaluations or len(combinations)
    return combinations[:limit]
