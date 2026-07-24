from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase7.consistency import add_cross_asset_consistency
from src.research.phase7.gates import evaluate_gates
from src.research.phase7.lifecycle import assign_lifecycle
from src.research.phase7.models import EvaluationResult, Phase7Config
from src.research.phase7.promotion_metrics import enrich_promotion_metrics
from src.research.phase7.scoring import composite_score

_REQUIRED_COLUMNS = {
    "strategy",
    "symbol",
    "oos_total_return",
    "oos_sharpe_ratio",
    "oos_max_drawdown",
    "oos_excess_cagr",
    "completed_trades",
}


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _defaults(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    defaults: dict[str, float] = {
        "parameter_stability": 0.0,
        "cost_resilience": 0.0,
    }
    for column, value in defaults.items():
        if column not in result:
            result[column] = value
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(value)
    return result


def _initial_evaluations(
    frame: pd.DataFrame,
    config: Phase7Config,
) -> list[EvaluationResult]:
    records: list[EvaluationResult] = []
    for _, row in frame.iterrows():
        metrics = {str(key): value for key, value in row.to_dict().items()}
        score = composite_score(metrics, config.weights)
        gate_results = evaluate_gates(metrics, config.gates, score)
        records.append(
            EvaluationResult(
                strategy=str(row["strategy"]),
                symbol=str(row["symbol"]),
                composite_score=score,
                lifecycle_state="REJECTED",
                paper_eligible=False,
                gate_results=gate_results,
                metrics=metrics,
            )
        )
    return records


def _finalize(
    records: list[EvaluationResult],
) -> tuple[list[EvaluationResult], list[dict[str, object]]]:
    by_symbol: dict[str, list[EvaluationResult]] = {}
    for item in records:
        by_symbol.setdefault(item.symbol, []).append(item)
    finalized: list[EvaluationResult] = []
    ranked_rows: list[dict[str, object]] = []
    for symbol, items in by_symbol.items():
        ordered = sorted(items, key=lambda item: item.composite_score, reverse=True)
        for rank, item in enumerate(ordered, start=1):
            state = assign_lifecycle(item.composite_score, item.gate_results, rank)
            final = EvaluationResult(
                strategy=item.strategy,
                symbol=symbol,
                composite_score=item.composite_score,
                lifecycle_state=state,
                paper_eligible=state == "PAPER-TRADING ELIGIBLE",
                gate_results=item.gate_results,
                metrics=item.metrics,
            )
            finalized.append(final)
            ranked_rows.append(
                {
                    "rank": rank,
                    "strategy": final.strategy,
                    "symbol": symbol,
                    "composite_score": final.composite_score,
                    "lifecycle_state": final.lifecycle_state,
                    "paper_eligible": final.paper_eligible,
                    "failed_gates": ",".join(
                        gate.name for gate in final.gate_results if not gate.passed
                    ),
                    **final.metrics,
                }
            )
    return finalized, ranked_rows


def run_phase7_selection(
    tournament_csv: Path,
    output_root: Path,
    config: Phase7Config | None = None,
) -> dict[str, object]:
    active = config or Phase7Config()
    frame = _defaults(pd.read_csv(tournament_csv))
    missing = _REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"tournament report missing columns: {sorted(missing)}")
    frame = add_cross_asset_consistency(frame)
    frame, regime_rows, monte_carlo_rows = enrich_promotion_metrics(
        frame,
        tournament_csv,
        runs=active.monte_carlo_runs,
        seed=active.seed,
        confidence=active.confidence_level,
    )
    finalized, ranked_rows = _finalize(_initial_evaluations(frame, active))
    leaderboard = pd.DataFrame(ranked_rows).sort_values(["symbol", "rank"])
    output_root.mkdir(parents=True, exist_ok=True)
    leaderboard.to_csv(output_root / "phase7_leaderboard.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(output_root / "regime_validation.csv", index=False)
    pd.DataFrame(monte_carlo_rows).to_csv(output_root / "monte_carlo_validation.csv", index=False)
    promotion = leaderboard[leaderboard["paper_eligible"].astype(bool)]
    promotion.to_csv(output_root / "paper_trading_eligible.csv", index=False)
    rejection = leaderboard[~leaderboard["paper_eligible"].astype(bool)]
    rejection.to_csv(output_root / "rejections.csv", index=False)
    payload = [
        {
            "strategy": item.strategy,
            "symbol": item.symbol,
            "composite_score": item.composite_score,
            "lifecycle_state": item.lifecycle_state,
            "paper_eligible": item.paper_eligible,
            "gates": [asdict(gate) for gate in item.gate_results],
            "metrics": item.metrics,
        }
        for item in finalized
    ]
    report = json.dumps(payload, indent=2, default=str)
    (output_root / "promotion_report.json").write_text(report, encoding="utf-8")
    manifest = {
        "phase": "7.10.0",
        "source_report": str(tournament_csv),
        "source_sha256": _fingerprint(tournament_csv),
        "rows": len(leaderboard),
        "eligible": len(promotion),
        "promotion_metrics_complete": True,
        "seed": active.seed,
        "monte_carlo_runs": active.monte_carlo_runs,
        "config": asdict(active),
    }
    manifest_text = json.dumps(manifest, indent=2)
    (output_root / "manifest.json").write_text(manifest_text, encoding="utf-8")
    return {
        "evaluations": len(leaderboard),
        "eligible": len(promotion),
        "promotion_metrics_complete": True,
        "output": str(output_root),
    }
