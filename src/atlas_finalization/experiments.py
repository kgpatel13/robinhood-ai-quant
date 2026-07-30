from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from src.atlas_finalization.models import ExperimentRecord


class ExperimentRegistry:
    def __init__(self) -> None:
        self._records: dict[str, ExperimentRecord] = {}

    def add(self, record: ExperimentRecord) -> None:
        if record.experiment_id in self._records:
            raise ValueError(f"duplicate experiment_id: {record.experiment_id}")
        self._records[record.experiment_id] = record

    def get(self, experiment_id: str) -> ExperimentRecord:
        try:
            return self._records[experiment_id]
        except KeyError as exc:
            raise KeyError(f"unknown experiment_id: {experiment_id}") from exc

    def list(self) -> tuple[ExperimentRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda item: item.created_at))

    @staticmethod
    def fingerprint(record: ExperimentRecord) -> str:
        payload = {
            "strategy_id": record.strategy_id,
            "strategy_version": record.strategy_version,
            "code_version": record.code_version,
            "dataset_id": record.dataset_id,
            "parameters": record.parameters,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def write_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = [self._serialize(record) for record in self.list()]
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(target)
        return target

    @staticmethod
    def _serialize(record: ExperimentRecord) -> dict[str, object]:
        payload = asdict(record)
        payload["created_at"] = record.created_at.isoformat()
        return payload
