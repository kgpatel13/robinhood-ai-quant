from __future__ import annotations

from dataclasses import dataclass

from src.execution.models import AccountSnapshot


@dataclass(frozen=True)
class PositionDifference:
    symbol: str
    expected_quantity: float
    actual_quantity: float


@dataclass(frozen=True)
class ReconciliationReport:
    differences: tuple[PositionDifference, ...]

    @property
    def in_sync(self) -> bool:
        return not self.differences


class PortfolioSync:
    @staticmethod
    def reconcile(
        expected: dict[str, float], actual: AccountSnapshot, *, tolerance: float = 1e-8
    ) -> ReconciliationReport:
        actual_map = {position.symbol: position.quantity for position in actual.positions}
        differences: list[PositionDifference] = []
        for symbol in sorted(set(expected) | set(actual_map)):
            expected_quantity = expected.get(symbol, 0.0)
            actual_quantity = actual_map.get(symbol, 0.0)
            if abs(expected_quantity - actual_quantity) > tolerance:
                differences.append(PositionDifference(symbol, expected_quantity, actual_quantity))
        return ReconciliationReport(tuple(differences))
