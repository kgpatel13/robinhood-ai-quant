from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict

from src.alpha_intelligence.models import AlphaCandidate, ExperimentRecord, PromotionStage


class ExperimentCatalog:
    def __init__(self, records: Iterable[ExperimentRecord] = ()) -> None:
        self._records: dict[str, ExperimentRecord] = {
            record.experiment_id: record for record in records
        }

    @staticmethod
    def fingerprint(strategy_id: str, dataset_id: str, parameters: dict[str, object]) -> str:
        payload = json.dumps(
            {"strategy_id": strategy_id, "dataset_id": dataset_id, "parameters": parameters},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def add(
        self,
        experiment_id: str,
        dataset_id: str,
        candidate: AlphaCandidate,
        stage: PromotionStage = PromotionStage.RESEARCH,
    ) -> ExperimentRecord:
        if experiment_id in self._records:
            raise ValueError(f"experiment already exists: {experiment_id}")
        record = ExperimentRecord(
            experiment_id=experiment_id,
            strategy_id=candidate.strategy_id,
            dataset_id=dataset_id,
            candidate=candidate,
            stage=stage,
            fingerprint=self.fingerprint(candidate.strategy_id, dataset_id, candidate.parameters),
        )
        self._records[experiment_id] = record
        return record

    def get(self, experiment_id: str) -> ExperimentRecord:
        return self._records[experiment_id]

    def list(self) -> tuple[ExperimentRecord, ...]:
        return tuple(self._records.values())

    def to_json(self) -> str:
        return json.dumps([asdict(record) for record in self.list()], default=str, sort_keys=True)
