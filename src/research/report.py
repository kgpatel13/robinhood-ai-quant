from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.research.models import OptimizationResult


def _rows(result: OptimizationResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for trial in result.trials:
        row: dict[str, object] = {"rank": trial.rank, "score": trial.score}
        row.update({f"parameter_{key}": value for key, value in trial.parameters.items()})
        row.update(trial.metrics)
        rows.append(row)
    return rows


def write_optimization_report(
    result: OptimizationResult, output_root: Path, report_name: str
) -> dict[str, Path]:
    directory = output_root / report_name
    directory.mkdir(parents=True, exist_ok=True)
    leaderboard = pd.DataFrame(_rows(result))
    csv_path = directory / "leaderboard.csv"
    json_path = directory / "leaderboard.json"
    metadata_path = directory / "metadata.json"
    equity_path = directory / "equity_best.csv"
    chart_path = directory / "equity_best.png"
    html_path = directory / "summary.html"
    leaderboard.to_csv(csv_path, index=False)
    json_path.write_text(leaderboard.to_json(orient="records", indent=2), encoding="utf-8")
    metadata = {
        "strategy": result.config.strategy,
        "method": result.config.method,
        "objective": result.config.objective,
        "seed": result.config.seed,
        "workers": result.config.workers,
        "evaluations": len(result.trials),
        "parameters": [asdict(item) for item in result.config.parameters],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    equity = cast(pd.DataFrame, result.best_equity_curve)
    equity.to_csv(equity_path, index=False)
    figure, axis = plt.subplots()
    axis.plot(equity["timestamp"], equity["equity"])
    axis.set_title("Best Optimization Trial")
    axis.set_xlabel("Date")
    axis.set_ylabel("Equity")
    figure.tight_layout()
    figure.savefig(chart_path)
    plt.close(figure)
    html_path.write_text(
        "<html><body><h1>Optimization Summary</h1>"
        f"<p>Strategy: {result.config.strategy}</p>"
        f"<p>Objective: {result.config.objective}</p>"
        + leaderboard.head(25).to_html(index=False)
        + '<p><img src="equity_best.png" alt="Best equity curve"></p></body></html>',
        encoding="utf-8",
    )
    return {
        "leaderboard_csv": csv_path,
        "leaderboard_json": json_path,
        "metadata": metadata_path,
        "best_equity_csv": equity_path,
        "best_equity_chart": chart_path,
        "summary_html": html_path,
    }
