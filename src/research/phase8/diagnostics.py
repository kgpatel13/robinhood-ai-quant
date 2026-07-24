from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.research.phase8.models import GateDiagnostic


def _gap(actual: float, threshold: float, comparison: str) -> float:
    if comparison in {">=", ">"}:
        return actual - threshold
    if comparison in {"<=", "<"}:
        return threshold - actual
    return 0.0


def build_gate_diagnostics(promotion_report: Path) -> list[GateDiagnostic]:
    payload = json.loads(promotion_report.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("promotion report must contain a list")
    records: list[GateDiagnostic] = []
    for evaluation in payload:
        if not isinstance(evaluation, dict):
            continue
        strategy = str(evaluation.get("strategy", ""))
        symbol = str(evaluation.get("symbol", ""))
        gates = evaluation.get("gates", [])
        if not isinstance(gates, list):
            continue
        for gate in gates:
            if not isinstance(gate, dict):
                continue
            actual = float(gate.get("actual", 0.0))
            threshold = float(gate.get("threshold", 0.0))
            comparison = str(gate.get("comparison", ">="))
            gap = _gap(actual, threshold, comparison)
            denominator = abs(threshold) if abs(threshold) > 1e-12 else 1.0
            records.append(
                GateDiagnostic(
                    strategy=strategy,
                    symbol=symbol,
                    gate=str(gate.get("name", "unknown")),
                    passed=bool(gate.get("passed", False)),
                    actual=actual,
                    threshold=threshold,
                    comparison=comparison,
                    gap=gap,
                    normalized_gap=gap / denominator,
                )
            )
    return records


def write_diagnostic_reports(promotion_report: Path, output_root: Path) -> dict[str, str]:
    records = build_gate_diagnostics(promotion_report)
    output_root.mkdir(parents=True, exist_ok=True)
    rows = [record.__dict__ for record in records]
    detail = pd.DataFrame(rows)
    detail_path = output_root / "threshold_gap_report.csv"
    detail.to_csv(detail_path, index=False)
    if detail.empty:
        matrix = pd.DataFrame()
        summary = pd.DataFrame()
    else:
        matrix = detail.pivot_table(
            index=["strategy", "symbol"], columns="gate", values="passed", aggfunc="first"
        ).reset_index()
        failures = detail[~detail["passed"].astype(bool)].copy()
        failures["severity"] = -failures["normalized_gap"]
        primary = (
            failures.sort_values("severity", ascending=False)
            .groupby(["strategy", "symbol"], as_index=False)
            .first()[["strategy", "symbol", "gate", "gap", "severity"]]
            .rename(columns={"gate": "primary_failure", "gap": "primary_gap"})
        )
        counts = (
            failures.groupby(["strategy", "symbol"], as_index=False)
            .size()
            .rename(columns={"size": "failed_gate_count"})
        )
        summary = counts.merge(primary, on=["strategy", "symbol"], how="left")
    matrix_path = output_root / "gate_failure_matrix.csv"
    summary_path = output_root / "strategy_diagnostics.csv"
    matrix.to_csv(matrix_path, index=False)
    summary.to_csv(summary_path, index=False)
    return {
        "threshold_gap_report": str(detail_path),
        "gate_failure_matrix": str(matrix_path),
        "strategy_diagnostics": str(summary_path),
    }
