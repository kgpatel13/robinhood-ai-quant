from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.models import OptimizationConfig, ParameterSpec
from src.research.phase5 import run_phase5_bundle
from src.research.phase7 import Phase7Config, run_phase7_selection
from src.research.phase8.diagnostics import write_diagnostic_reports
from src.research.phase8.experiment_store import ExperimentStore
from src.research.phase8.features import write_feature_snapshots
from src.research.phase8.models import CandidateDefinition, Phase8Config, Phase8Result
from src.research.phase8.ranking import build_candidate_ranking
from src.research.phase8.search_space import generate_candidates
from src.research.phase8.stability import apply_neighborhood_stability
from src.research.validation import discover_datasets
from src.research.walk_forward import WalkForwardConfig
from src.strategies import available_strategies


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _summary_count(summary: dict[str, object], key: str) -> int:
    value = summary.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    raise TypeError(f"Promotion summary field {key!r} must be numeric, got {type(value).__name__}")


def _candidate_optimization(
    candidate: CandidateDefinition, config: Phase8Config
) -> OptimizationConfig:
    return OptimizationConfig(
        strategy=candidate.strategy,
        parameters=tuple(
            ParameterSpec(name, (value,)) for name, value in sorted(candidate.parameters.items())
        ),
        method="grid",
        objective=config.objective,
        max_evaluations=1,
        seed=config.seed,
        workers=config.workers,
        initial_cash=config.initial_cash,
        commission_per_trade=config.commission_per_trade,
        slippage_bps=config.equity_slippage_bps,
        fee_bps=config.equity_fee_bps,
    )


def _copy_candidate_evidence(
    candidate_root: Path, tournament_root: Path, candidate_id: str
) -> None:
    destination = tournament_root / candidate_id
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(candidate_root, destination)


def run_phase8_discovery(data_root: Path, config: Phase8Config) -> Phase8Result:
    experiment_id = f"phase8-{uuid.uuid4().hex[:12]}"
    output = config.output_root
    output.mkdir(parents=True, exist_ok=True)
    store = ExperimentStore(config.database_path)
    store.create_experiment(experiment_id, asdict(config), output)
    registry = discover_datasets(data_root)
    unknown = sorted(set(config.symbols).difference(registry))
    if unknown:
        store.set_experiment_status(experiment_id, "FAILED")
        raise ValueError(f"Unknown symbols: {unknown}")
    selected_strategies = list(config.strategies) or available_strategies()
    candidates = generate_candidates(
        selected_strategies,
        config.max_candidates_per_strategy,
        config.search_method,
        config.seed,
    )
    feature_paths = write_feature_snapshots(registry, config.symbols, output / "features")
    tournament_root = output / "tournament"
    tournament_root.mkdir(parents=True, exist_ok=True)
    walk_forward = WalkForwardConfig(
        training_years=config.training_years,
        testing_years=config.testing_years,
        step_years=config.step_years,
        minimum_test_rows=config.minimum_test_rows,
    )
    rows: list[pd.DataFrame] = []
    evaluated = 0
    cached = 0
    for candidate in candidates:
        candidate_root = output / "candidate_runs" / candidate.candidate_id
        leaderboard_path = candidate_root / "phase5_leaderboard.csv"
        if config.resume and leaderboard_path.exists():
            cached += 1
            store.upsert_candidate(experiment_id, candidate, "CACHED")
        else:
            store.upsert_candidate(experiment_id, candidate, "RUNNING")
            try:
                run_phase5_bundle(
                    data_root,
                    list(config.symbols),
                    _candidate_optimization(candidate, config),
                    walk_forward,
                    candidate_root,
                    crypto_fee_bps=config.crypto_fee_bps,
                    crypto_slippage_bps=config.crypto_slippage_bps,
                )
            except Exception as exc:
                store.upsert_candidate(experiment_id, candidate, "FAILED", str(exc))
                continue
            evaluated += 1
            store.upsert_candidate(experiment_id, candidate, "COMPLETED")
        _copy_candidate_evidence(candidate_root, tournament_root, candidate.candidate_id)
        leaderboard = pd.read_csv(leaderboard_path)
        leaderboard.insert(0, "strategy", candidate.candidate_id)
        leaderboard.insert(1, "base_strategy", candidate.strategy)
        leaderboard.insert(2, "parameters_json", json.dumps(candidate.parameters, sort_keys=True))
        leaderboard.insert(3, "candidate_source", candidate.source)
        rows.append(leaderboard)
    if not rows:
        store.set_experiment_status(experiment_id, "FAILED")
        raise RuntimeError("No candidate completed successfully")
    tournament = pd.concat(rows, ignore_index=True)
    tournament = apply_neighborhood_stability(
        tournament,
        tolerance=config.neighborhood_score_tolerance,
        minimum_neighbors=config.minimum_neighbors,
    )
    tournament_csv = tournament_root / "strategy_tournament.csv"
    tournament.to_csv(tournament_csv, index=False)
    phase7_root = output / "promotion"
    promotion_summary = run_phase7_selection(
        tournament_csv,
        phase7_root,
        Phase7Config(seed=config.seed, monte_carlo_runs=config.monte_carlo_runs),
    )
    diagnostics = write_diagnostic_reports(
        phase7_root / "promotion_report.json", output / "diagnostics"
    )
    leaderboard = pd.read_csv(phase7_root / "phase7_leaderboard.csv")
    ranking = build_candidate_ranking(leaderboard)
    ranking_path = output / "candidate_ranking.csv"
    ranking.to_csv(ranking_path, index=False)
    manifest = {
        "phase": "8.9.0",
        "experiment_id": experiment_id,
        "config": asdict(config),
        "candidate_count": len(candidates),
        "evaluated": evaluated,
        "cached": cached,
        "evaluations": _summary_count(promotion_summary, "evaluations"),
        "eligible": _summary_count(promotion_summary, "eligible"),
        "artifacts": {
            "tournament": str(tournament_csv),
            "candidate_ranking": str(ranking_path),
            "features": feature_paths,
            **diagnostics,
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    for name, path in {
        "manifest": manifest_path,
        "tournament": tournament_csv,
        "candidate_ranking": ranking_path,
    }.items():
        store.add_artifact(experiment_id, name, path, _sha256(path))
    store.set_experiment_status(experiment_id, "COMPLETED")
    return Phase8Result(
        experiment_id=experiment_id,
        candidates_generated=len(candidates),
        candidates_evaluated=evaluated,
        candidates_cached=cached,
        evaluations=_summary_count(promotion_summary, "evaluations"),
        eligible=_summary_count(promotion_summary, "eligible"),
        output=str(output),
        artifacts={
            "manifest": str(manifest_path),
            "candidate_ranking": str(ranking_path),
            **diagnostics,
        },
    )
