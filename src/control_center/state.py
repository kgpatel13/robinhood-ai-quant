from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from src.control_center.models import IntradaySessionState, PaperPosition


class IntradayStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: IntradaySessionState) -> None:
        payload = asdict(state)
        payload["positions"] = {
            symbol: _position_payload(position) for symbol, position in state.positions.items()
        }
        payload["cooldown_until"] = {
            symbol: value.isoformat() for symbol, value in state.cooldown_until.items()
        }
        payload["processed_decision_ids"] = sorted(state.processed_decision_ids)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> IntradaySessionState:
        raw = cast(dict[str, Any], json.loads(self.path.read_text(encoding="utf-8")))
        positions = {
            symbol: _position_from_payload(cast(dict[str, Any], value))
            for symbol, value in cast(dict[str, Any], raw.pop("positions")).items()
        }
        cooldown_until = {
            symbol: datetime.fromisoformat(value)
            for symbol, value in cast(dict[str, str], raw.pop("cooldown_until")).items()
        }
        processed = set(cast(list[str], raw.pop("processed_decision_ids")))
        return IntradaySessionState(
            **raw,
            positions=positions,
            cooldown_until=cooldown_until,
            processed_decision_ids=processed,
        )

    def load_or_create(self, session_date: str, starting_equity: float) -> IntradaySessionState:
        if not self.path.exists():
            return IntradaySessionState(session_date, starting_equity)
        state = self.load()
        if state.session_date != session_date:
            return IntradaySessionState(session_date, starting_equity)
        return state


def _position_payload(position: PaperPosition) -> dict[str, Any]:
    payload = asdict(position)
    payload["opened_at"] = position.opened_at.isoformat() if position.opened_at else None
    return payload


def _position_from_payload(payload: dict[str, Any]) -> PaperPosition:
    opened_at = payload.get("opened_at")
    payload["opened_at"] = datetime.fromisoformat(opened_at) if opened_at else None
    return PaperPosition(**payload)
