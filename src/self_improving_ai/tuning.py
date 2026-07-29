from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

type ParameterValue = int | float | str | bool
type ParameterSet = Mapping[str, ParameterValue]


@dataclass(frozen=True, slots=True)
class TuningResult:
    parameters: dict[str, ParameterValue]
    score: float


class AdaptiveParameterTuner:
    def tune(
        self,
        candidates: Iterable[ParameterSet],
        objective: Callable[[ParameterSet], float],
    ) -> TuningResult:
        best_parameters: dict[str, ParameterValue] | None = None
        best_score = float("-inf")
        for candidate in candidates:
            score = float(objective(candidate))
            if score > best_score:
                best_score = score
                best_parameters = dict(candidate)
        if best_parameters is None:
            raise ValueError("at least one candidate parameter set is required")
        return TuningResult(parameters=best_parameters, score=best_score)
