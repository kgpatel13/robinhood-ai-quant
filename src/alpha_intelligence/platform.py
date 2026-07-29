from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.alpha_intelligence.experiments import ExperimentCatalog
from src.alpha_intelligence.models import AlphaCandidate, PromotionStage, SearchMethod
from src.alpha_intelligence.robustness import RobustnessEvaluator
from src.alpha_intelligence.search import ParameterSearch

CandidateEvaluator = Callable[[str, dict[str, Any]], AlphaCandidate]


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates: tuple[AlphaCandidate, ...]
    champion: AlphaCandidate | None


class AlphaIntelligencePlatform:
    def __init__(
        self,
        robustness: RobustnessEvaluator | None = None,
        catalog: ExperimentCatalog | None = None,
    ) -> None:
        self.robustness = robustness or RobustnessEvaluator()
        self.catalog = catalog or ExperimentCatalog()
        self.search = ParameterSearch()

    def discover(
        self,
        strategy_id: str,
        dataset_id: str,
        search_space: Mapping[str, Sequence[Any]],
        evaluator: CandidateEvaluator,
        method: SearchMethod = SearchMethod.GRID,
        maximum_candidates: int | None = None,
        seed: int = 0,
    ) -> DiscoveryResult:
        parameter_sets = self.search.generate(search_space, method, maximum_candidates, seed)
        assessed: list[AlphaCandidate] = []
        for index, parameters in enumerate(parameter_sets, start=1):
            raw = evaluator(strategy_id, parameters)
            candidate = self.robustness.evaluate(raw)
            assessed.append(candidate)
            self.catalog.add(
                experiment_id=f"{strategy_id}-{index:04d}",
                dataset_id=dataset_id,
                candidate=candidate,
                stage=PromotionStage.RESEARCH,
            )
        ranked = tuple(sorted(assessed, key=lambda item: item.score, reverse=True))
        champion = next((item for item in ranked if not item.rejection_reasons), None)
        return DiscoveryResult(ranked, champion)
