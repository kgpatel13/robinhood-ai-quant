from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from src.backtest.models import BacktestResult


def write_backtest_report(result: BacktestResult, output_dir: Path, name: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace("/", "-").replace(" ", "_")
    metrics_path = output_dir / f"{safe_name}_metrics.json"
    equity_path = output_dir / f"{safe_name}_equity.csv"
    trades_path = output_dir / f"{safe_name}_trades.csv"
    equity_chart_path = output_dir / f"{safe_name}_equity.png"
    drawdown_chart_path = output_dir / f"{safe_name}_drawdown.png"

    metrics_path.write_text(json.dumps(result.metrics, indent=2), encoding="utf-8")
    result.equity_curve.to_csv(equity_path, index=False)
    result.trades.to_csv(trades_path, index=False)

    figure, axis = plt.subplots()
    axis.plot(result.equity_curve["timestamp"], result.equity_curve["equity"])
    axis.set_title("Equity Curve")
    axis.set_xlabel("Date")
    axis.set_ylabel("Equity")
    figure.tight_layout()
    figure.savefig(equity_chart_path, dpi=140)
    plt.close(figure)

    equity = result.equity_curve["equity"]
    drawdown = equity / equity.cummax() - 1.0
    figure, axis = plt.subplots()
    axis.plot(result.equity_curve["timestamp"], drawdown)
    axis.set_title("Drawdown")
    axis.set_xlabel("Date")
    axis.set_ylabel("Drawdown")
    figure.tight_layout()
    figure.savefig(drawdown_chart_path, dpi=140)
    plt.close(figure)

    return {
        "metrics": metrics_path,
        "equity": equity_path,
        "trades": trades_path,
        "equity_chart": equity_chart_path,
        "drawdown_chart": drawdown_chart_path,
    }
