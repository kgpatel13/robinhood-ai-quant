from __future__ import annotations

import hashlib
import itertools
import json
import random

from src.research.phase8.models import CandidateDefinition
from src.strategies import strategy_defaults, strategy_parameter_space


def candidate_id(strategy: str, parameters: dict[str, int | float]) -> str:
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{strategy}:{canonical}".encode()).hexdigest()[:12]
    return f"{strategy}__{digest}"


def _valid_ordering(parameters: dict[str, int | float]) -> bool:
    pairs = (
        ("fast_window", "slow_window"),
        ("entry_window", "exit_window"),
        ("short_window", "long_window"),
    )
    for lower, upper in pairs:
        if (
            lower in parameters
            and upper in parameters
            and float(parameters[lower]) >= float(parameters[upper])
        ):
            return False
    return not (
        "oversold" in parameters
        and "overbought" in parameters
        and float(parameters["oversold"]) >= float(parameters["overbought"])
    )


def generate_strategy_candidates(
    strategy: str,
    *,
    maximum: int,
    method: str = "hybrid",
    seed: int = 42,
) -> list[CandidateDefinition]:
    specs = strategy_parameter_space(strategy)
    names = [item.name for item in specs]
    combinations = [
        dict(zip(names, values, strict=True))
        for values in itertools.product(*(item.values for item in specs))
    ]
    combinations = [item for item in combinations if _valid_ordering(item)]
    defaults = strategy_defaults(strategy)
    selected: list[tuple[dict[str, int | float], str]] = []
    if defaults in combinations:
        selected.append((defaults, "default"))
    grid_limit = maximum if method == "grid" else max(1, maximum // 2)
    if method in {"grid", "hybrid"}:
        for parameters in combinations:
            if parameters != defaults:
                selected.append((parameters, "grid"))
            if len(selected) >= grid_limit:
                break
    if method in {"random", "hybrid"} and len(selected) < maximum:
        rng = random.Random(seed + sum(ord(char) for char in strategy))
        remaining = [item for item in combinations if item not in [row[0] for row in selected]]
        rng.shuffle(remaining)
        selected.extend((item, "random") for item in remaining[: maximum - len(selected)])
    unique: dict[str, CandidateDefinition] = {}
    for parameters, source in selected[:maximum]:
        identifier = candidate_id(strategy, parameters)
        unique[identifier] = CandidateDefinition(identifier, strategy, parameters, source)
    return list(unique.values())


def generate_candidates(
    strategies: list[str], maximum_per_strategy: int, method: str, seed: int
) -> list[CandidateDefinition]:
    result: list[CandidateDefinition] = []
    for strategy in strategies:
        result.extend(
            generate_strategy_candidates(
                strategy,
                maximum=maximum_per_strategy,
                method=method,
                seed=seed,
            )
        )
    return result
