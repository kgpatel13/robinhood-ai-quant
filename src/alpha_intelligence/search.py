from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from itertools import product
from typing import Any

from src.alpha_intelligence.models import SearchMethod


class ParameterSearch:
    def generate(
        self,
        search_space: Mapping[str, Sequence[Any]],
        method: SearchMethod = SearchMethod.GRID,
        maximum_candidates: int | None = None,
        seed: int = 0,
    ) -> tuple[dict[str, Any], ...]:
        if maximum_candidates is not None and maximum_candidates < 1:
            raise ValueError("maximum_candidates must be positive")
        keys = tuple(sorted(search_space))
        values = tuple(tuple(search_space[key]) for key in keys)
        if any(not options for options in values):
            raise ValueError("search-space values cannot be empty")
        candidates = [dict(zip(keys, combination, strict=True)) for combination in product(*values)]
        if method is SearchMethod.RANDOM:
            generator = random.Random(seed)
            generator.shuffle(candidates)
        if maximum_candidates is not None:
            candidates = candidates[:maximum_candidates]
        return tuple(candidates)
