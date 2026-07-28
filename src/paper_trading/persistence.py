from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.paper_trading.models import PaperAccount, PaperPosition


class PaperAccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, account: PaperAccount) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "starting_cash": account.starting_cash,
            "cash": account.cash,
            "realized_pnl": account.realized_pnl,
            "positions": {
                symbol: asdict(position) for symbol, position in account.positions.items()
            },
        }
        serialized_positions = payload["positions"]
        if not isinstance(serialized_positions, dict):
            raise TypeError("serialized paper positions must be a dictionary")
        for position in serialized_positions.values():
            if not isinstance(position, dict):
                raise TypeError("serialized paper position must be a dictionary")
            opened_at = position.get("opened_at")
            if not isinstance(opened_at, datetime):
                raise TypeError("paper position opened_at must be a datetime")
            position["opened_at"] = opened_at.isoformat()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    def load(self, default_cash: float) -> PaperAccount:
        if not self.path.exists():
            return PaperAccount(starting_cash=default_cash, cash=default_cash)
        payload: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        positions = {
            symbol: PaperPosition(
                symbol=value["symbol"],
                quantity=int(value["quantity"]),
                average_price=float(value["average_price"]),
                strategy=value["strategy"],
                opened_at=datetime.fromisoformat(value["opened_at"]),
                last_price=float(value["last_price"]),
            )
            for symbol, value in payload.get("positions", {}).items()
        }
        return PaperAccount(
            starting_cash=float(payload["starting_cash"]),
            cash=float(payload["cash"]),
            realized_pnl=float(payload.get("realized_pnl", 0.0)),
            positions=positions,
        )
