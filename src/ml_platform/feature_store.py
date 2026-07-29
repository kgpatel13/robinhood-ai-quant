from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FeatureSetDefinition:
    name: str
    version: str
    entity_keys: tuple[str, ...]
    timestamp_column: str
    feature_columns: tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("feature-set name and version must not be empty")
        if not self.entity_keys:
            raise ValueError("at least one entity key is required")
        if not self.feature_columns:
            raise ValueError("at least one feature column is required")
        reserved = set(self.entity_keys) | {self.timestamp_column}
        if reserved.intersection(self.feature_columns):
            raise ValueError("feature columns must not duplicate keys or timestamp")

    @property
    def identifier(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(frozen=True)
class FeatureSnapshot:
    identifier: str
    created_at: datetime
    rows: int
    minimum_timestamp: datetime
    maximum_timestamp: datetime
    content_hash: str
    data_path: Path


class OfflineFeatureStore:
    """Versioned, point-in-time-safe Parquet feature storage."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, definition: FeatureSetDefinition, frame: pd.DataFrame) -> FeatureSnapshot:
        required = [
            *definition.entity_keys,
            definition.timestamp_column,
            *definition.feature_columns,
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"missing feature-store columns: {missing}")
        clean = frame.loc[:, required].copy()
        clean[definition.timestamp_column] = pd.to_datetime(
            clean[definition.timestamp_column], utc=True, errors="raise"
        )
        clean = clean.sort_values([*definition.entity_keys, definition.timestamp_column])
        if clean.duplicated([*definition.entity_keys, definition.timestamp_column]).any():
            raise ValueError("duplicate entity/timestamp feature rows are not allowed")
        if clean.empty:
            raise ValueError("feature frame must not be empty")

        directory = self._directory(definition)
        directory.mkdir(parents=True, exist_ok=True)
        data_path = directory / "features.parquet"
        clean.to_parquet(data_path, index=False)
        content_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
        created_at = datetime.now(UTC)
        metadata: dict[str, Any] = {
            "definition": asdict(definition),
            "created_at": created_at.isoformat(),
            "rows": len(clean),
            "minimum_timestamp": clean[definition.timestamp_column].min().isoformat(),
            "maximum_timestamp": clean[definition.timestamp_column].max().isoformat(),
            "content_hash": content_hash,
        }
        (directory / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        return self.describe(definition)

    def read(
        self,
        definition: FeatureSetDefinition,
        *,
        as_of: datetime | None = None,
        entities: dict[str, tuple[str, ...]] | None = None,
    ) -> pd.DataFrame:
        frame = pd.read_parquet(self._directory(definition) / "features.parquet")
        timestamp = definition.timestamp_column
        frame[timestamp] = pd.to_datetime(frame[timestamp], utc=True)
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            if cutoff.tzinfo is None:
                cutoff = cutoff.tz_localize("UTC")
            else:
                cutoff = cutoff.tz_convert("UTC")
            frame = frame.loc[frame[timestamp] <= cutoff]
        for key, values in (entities or {}).items():
            if key not in definition.entity_keys:
                raise ValueError(f"unknown entity key: {key}")
            frame = frame.loc[frame[key].astype(str).isin(values)]
        return frame.reset_index(drop=True)

    def latest_by_entity(
        self, definition: FeatureSetDefinition, *, as_of: datetime
    ) -> pd.DataFrame:
        frame = self.read(definition, as_of=as_of)
        if frame.empty:
            return frame
        timestamp = definition.timestamp_column
        index = frame.groupby(list(definition.entity_keys), sort=False)[timestamp].idxmax()
        return frame.loc[index].sort_values(list(definition.entity_keys)).reset_index(drop=True)

    def describe(self, definition: FeatureSetDefinition) -> FeatureSnapshot:
        directory = self._directory(definition)
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        return FeatureSnapshot(
            identifier=definition.identifier,
            created_at=datetime.fromisoformat(metadata["created_at"]),
            rows=int(metadata["rows"]),
            minimum_timestamp=datetime.fromisoformat(metadata["minimum_timestamp"]),
            maximum_timestamp=datetime.fromisoformat(metadata["maximum_timestamp"]),
            content_hash=str(metadata["content_hash"]),
            data_path=directory / "features.parquet",
        )

    def _directory(self, definition: FeatureSetDefinition) -> Path:
        return self.root / definition.name / definition.version
