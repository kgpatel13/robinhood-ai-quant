from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ResearchEntry:
    experiment_id: str
    strategy_version: str
    model_version: str
    feature_set: str
    market_regime: str
    metrics: dict[str, float]
    promotion_decision: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    assumptions: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


class ResearchJournal:
    """Append-only JSONL research audit trail."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, entry: ResearchEntry) -> None:
        if entry.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(entry)
        payload["created_at"] = entry.created_at.isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def entries(self) -> tuple[ResearchEntry, ...]:
        if not self.path.exists():
            return ()
        result: list[ResearchEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            result.append(
                ResearchEntry(
                    experiment_id=str(payload["experiment_id"]),
                    strategy_version=str(payload["strategy_version"]),
                    model_version=str(payload["model_version"]),
                    feature_set=str(payload["feature_set"]),
                    market_regime=str(payload["market_regime"]),
                    metrics={str(key): float(value) for key, value in payload["metrics"].items()},
                    promotion_decision=str(payload["promotion_decision"]),
                    created_at=datetime.fromisoformat(str(payload["created_at"])),
                    hyperparameters=dict(payload.get("hyperparameters", {})),
                    assumptions=dict(payload.get("assumptions", {})),
                    notes=str(payload.get("notes", "")),
                )
            )
        return tuple(result)

    def latest(self, strategy_version: str | None = None) -> ResearchEntry | None:
        candidates = [
            entry
            for entry in self.entries()
            if strategy_version is None or entry.strategy_version == strategy_version
        ]
        return max(candidates, key=lambda item: item.created_at) if candidates else None
