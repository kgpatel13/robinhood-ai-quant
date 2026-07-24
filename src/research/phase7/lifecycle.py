from __future__ import annotations

from src.research.phase7.models import GateResult, LifecycleState


def assign_lifecycle(score: float, gates: tuple[GateResult, ...], rank: int = 0) -> LifecycleState:
    all_pass = all(item.passed for item in gates)
    if all_pass:
        return "PAPER-TRADING ELIGIBLE"
    critical = {item.name: item.passed for item in gates}
    if score >= 75.0 and critical.get("positive_benchmark_alpha", False):
        return "CHAMPION" if rank == 1 else "CHALLENGER"
    if score >= 60.0:
        return "CANDIDATE"
    if score >= 40.0:
        return "EXPERIMENTAL"
    return "REJECTED"
