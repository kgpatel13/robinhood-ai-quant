from __future__ import annotations

import html
import json
from pathlib import Path

import matplotlib.pyplot as plt

from src.portfolio.models import PortfolioBacktestResult


def write_portfolio_report(
    result: PortfolioBacktestResult, output_dir: Path, name: str
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace("/", "-").replace(" ", "_")
    metrics_path = output_dir / f"{safe_name}_metrics.json"
    equity_path = output_dir / f"{safe_name}_equity.csv"
    trades_path = output_dir / f"{safe_name}_trades.csv"
    holdings_path = output_dir / f"{safe_name}_holdings.csv"
    weights_path = output_dir / f"{safe_name}_target_weights.csv"
    equity_chart_path = output_dir / f"{safe_name}_equity.png"
    drawdown_chart_path = output_dir / f"{safe_name}_drawdown.png"
    allocation_chart_path = output_dir / f"{safe_name}_allocations.png"
    html_path = output_dir / f"{safe_name}_report.html"

    metrics_path.write_text(json.dumps(result.metrics, indent=2), encoding="utf-8")
    result.equity_curve.to_csv(equity_path, index=False)
    result.trades.to_csv(trades_path, index=False)
    result.holdings.to_csv(holdings_path, index=False)
    result.target_weights.to_csv(weights_path, index=False)

    figure, axis = plt.subplots()
    axis.plot(result.equity_curve["timestamp"], result.equity_curve["equity"])
    axis.set_title("Portfolio Equity Curve")
    axis.set_xlabel("Date")
    axis.set_ylabel("Equity")
    figure.tight_layout()
    figure.savefig(equity_chart_path, dpi=140)
    plt.close(figure)

    equity = result.equity_curve["equity"]
    drawdown = equity / equity.cummax() - 1.0
    figure, axis = plt.subplots()
    axis.plot(result.equity_curve["timestamp"], drawdown)
    axis.set_title("Portfolio Drawdown")
    axis.set_xlabel("Date")
    axis.set_ylabel("Drawdown")
    figure.tight_layout()
    figure.savefig(drawdown_chart_path, dpi=140)
    plt.close(figure)

    weight_columns = [column for column in result.target_weights.columns if column != "timestamp"]
    figure, axis = plt.subplots()
    axis.stackplot(
        result.target_weights["timestamp"],
        *[result.target_weights[column] for column in weight_columns],
        labels=weight_columns,
    )
    axis.set_title("Target Allocation")
    axis.set_xlabel("Date")
    axis.set_ylabel("Weight")
    axis.legend(loc="upper left")
    figure.tight_layout()
    figure.savefig(allocation_chart_path, dpi=140)
    plt.close(figure)

    metric_rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in result.metrics.items()
    )
    html_path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="en"><head><meta charset="utf-8">',
                f"<title>{html.escape(safe_name)} portfolio report</title>",
                "<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:2rem auto;"
                "padding:0 1rem}table{border-collapse:collapse}th,td{border:1px solid #ccc;"
                "padding:.45rem;text-align:left}img{max-width:100%;margin:1rem 0}"
                "</style></head><body>",
                f"<h1>{html.escape(safe_name)} portfolio report</h1>",
                f"<table>{metric_rows}</table>",
                f'<h2>Equity</h2><img src="{equity_chart_path.name}" alt="Equity curve">',
                f'<h2>Drawdown</h2><img src="{drawdown_chart_path.name}" alt="Drawdown">',
                f'<h2>Allocation</h2><img src="{allocation_chart_path.name}" alt="Allocation">',
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "metrics": metrics_path,
        "equity": equity_path,
        "trades": trades_path,
        "holdings": holdings_path,
        "target_weights": weights_path,
        "equity_chart": equity_chart_path,
        "drawdown_chart": drawdown_chart_path,
        "allocation_chart": allocation_chart_path,
        "html_report": html_path,
    }
