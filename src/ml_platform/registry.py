from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import joblib


class ModelStage(StrEnum):
    CANDIDATE = "candidate"
    CHALLENGER = "challenger"
    CHAMPION = "champion"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class RegisteredModel:
    name: str
    version: str
    stage: ModelStage
    created_at: datetime
    metrics: dict[str, float]
    feature_set: str
    artifact_path: Path


class ModelRegistry:
    """Filesystem model registry with atomic stage transitions and rollback."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def register(
        self,
        *,
        name: str,
        version: str,
        model: Any,
        metrics: dict[str, float],
        feature_set: str,
        stage: ModelStage = ModelStage.CANDIDATE,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredModel:
        directory = self._directory(name, version)
        directory.mkdir(parents=True, exist_ok=False)
        joblib.dump(model, directory / "model.joblib")
        created_at = datetime.now(UTC)
        payload = {
            "name": name,
            "version": version,
            "stage": stage.value,
            "created_at": created_at.isoformat(),
            "metrics": metrics,
            "feature_set": feature_set,
            "metadata": metadata or {},
        }
        self._write_json(directory / "metadata.json", payload)
        return self.get(name, version)

    def get(self, name: str, version: str) -> RegisteredModel:
        directory = self._directory(name, version)
        payload = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        return RegisteredModel(
            name=str(payload["name"]),
            version=str(payload["version"]),
            stage=ModelStage(payload["stage"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            metrics={str(key): float(value) for key, value in payload["metrics"].items()},
            feature_set=str(payload["feature_set"]),
            artifact_path=directory / "model.joblib",
        )

    def load(self, name: str, version: str) -> Any:
        return joblib.load(self._directory(name, version) / "model.joblib")

    def list_versions(self, name: str) -> tuple[RegisteredModel, ...]:
        root = self.root / name
        if not root.exists():
            return ()
        models = [self.get(name, path.name) for path in root.iterdir() if path.is_dir()]
        return tuple(sorted(models, key=lambda item: item.created_at))

    def champion(self, name: str) -> RegisteredModel | None:
        champions = [
            model for model in self.list_versions(name) if model.stage is ModelStage.CHAMPION
        ]
        return champions[-1] if champions else None

    def promote(self, name: str, version: str) -> RegisteredModel:
        self.get(name, version)
        current = self.champion(name)
        if current is not None and current.version != version:
            self._set_stage(name, current.version, ModelStage.ARCHIVED)
        self._set_stage(name, version, ModelStage.CHAMPION)
        return self.get(name, version)

    def mark_challenger(self, name: str, version: str) -> RegisteredModel:
        self._set_stage(name, version, ModelStage.CHALLENGER)
        return self.get(name, version)

    def rollback(self, name: str, version: str) -> RegisteredModel:
        if self.get(name, version).stage is not ModelStage.ARCHIVED:
            raise ValueError("rollback target must be archived")
        return self.promote(name, version)

    def delete(self, name: str, version: str) -> None:
        model = self.get(name, version)
        if model.stage is ModelStage.CHAMPION:
            raise ValueError("champion model cannot be deleted")
        shutil.rmtree(self._directory(name, version))

    def _set_stage(self, name: str, version: str, stage: ModelStage) -> None:
        path = self._directory(name, version) / "metadata.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["stage"] = stage.value
        self._write_json(path, payload)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def _directory(self, name: str, version: str) -> Path:
        safe_name = name.strip().replace("/", "-").replace("\\", "-")
        safe_version = version.strip().replace("/", "-").replace("\\", "-")
        if not safe_name or not safe_version:
            raise ValueError("model name and version must not be empty")
        return self.root / safe_name / safe_version
