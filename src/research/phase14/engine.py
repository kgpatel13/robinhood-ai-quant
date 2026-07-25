from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.research.phase14.models import Phase14Config, Phase14Result

PHASE = "14.0-14.9"
VERSION = "0.14.0"

_CRYPTO_SUFFIXES = ("-USD", "-USDT", "-USDC")
_ETF_SYMBOLS = {"SPY", "QQQ", "VTI", "IWM", "DIA", "GLD", "TLT", "XLK", "XLF", "XLE", "XLV"}


def infer_asset_class(symbol: str, supplied: str | None = None) -> str:
    normalized = (supplied or "").strip().lower()
    if normalized and normalized not in {"unknown", "nan", "none"}:
        return normalized
    upper = symbol.upper()
    if upper.endswith(_CRYPTO_SUFFIXES):
        return "crypto"
    if upper in _ETF_SYMBOLS:
        return "etf"
    return "stock"


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0.0 else 0.0


def _maximum_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    peak = values.cummax()
    drawdown = 1.0 - values / peak.replace(0.0, np.nan)
    return float(drawdown.fillna(0.0).max())


def _years_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    seconds = max((end - start).total_seconds(), 0.0)
    return seconds / (365.2425 * 24.0 * 60.0 * 60.0)


def _reconstruct_realized_equity(trades: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    ordered = trades.sort_values(["exit_timestamp", "entry_timestamp"]).copy()
    ordered["capital"] = initial_capital + ordered["pnl"].astype(float).cumsum()
    return ordered[["exit_timestamp", "capital"]].rename(columns={"exit_timestamp": "timestamp"})


def _annualized_metrics(equity: pd.DataFrame, risk_free_rate: float) -> dict[str, float]:
    ordered = equity.sort_values("timestamp").drop_duplicates("timestamp", keep="last").copy()
    initial = float(ordered["capital"].iloc[0])
    final = float(ordered["capital"].iloc[-1])
    start = pd.Timestamp(ordered["timestamp"].iloc[0])
    end = pd.Timestamp(ordered["timestamp"].iloc[-1])
    years = _years_between(start, end)
    total_return = final / initial - 1.0 if initial > 0.0 else 0.0
    cagr = (
        (final / initial) ** (1.0 / years) - 1.0
        if initial > 0.0 and final > 0.0 and years > 0.0
        else 0.0
    )

    daily = (
        ordered.set_index("timestamp")["capital"]
        .resample("1D")
        .last()
        .ffill()
        .pct_change()
        .dropna()
    )
    annual_volatility = float(daily.std(ddof=1) * math.sqrt(365.0)) if len(daily) > 1 else 0.0
    annual_return = float(daily.mean() * 365.0) if not daily.empty else 0.0
    downside = daily[daily < 0.0]
    downside_deviation = (
        float(downside.std(ddof=1) * math.sqrt(365.0)) if len(downside) > 1 else 0.0
    )
    sharpe = _safe_ratio(annual_return - risk_free_rate, annual_volatility)
    sortino = _safe_ratio(annual_return - risk_free_rate, downside_deviation)
    max_drawdown = _maximum_drawdown(ordered["capital"].astype(float))
    calmar = _safe_ratio(cagr, max_drawdown)
    return {
        "initial_capital": initial,
        "final_capital": final,
        "total_return": total_return,
        "calendar_years": years,
        "cagr": cagr,
        "annualized_return": annual_return,
        "annualized_volatility": annual_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "maximum_drawdown": max_drawdown,
    }


def _trade_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    pnl = frame["pnl"].astype(float)
    returns = frame["net_return"].astype(float)
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    holding_days = (
        frame["exit_timestamp"] - frame["entry_timestamp"]
    ).dt.total_seconds() / 86_400.0
    return {
        "trades": int(len(frame)),
        "wins": int((pnl > 0.0).sum()),
        "losses": int((pnl < 0.0).sum()),
        "win_rate": float((pnl > 0.0).mean()) if len(frame) else 0.0,
        "net_pnl": float(pnl.sum()),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else 0.0,
        "expectancy_pnl": float(pnl.mean()) if len(frame) else 0.0,
        "average_net_return": float(returns.mean()) if len(frame) else 0.0,
        "median_net_return": float(returns.median()) if len(frame) else 0.0,
        "average_holding_days": float(holding_days.mean()) if len(frame) else 0.0,
    }


def _group_attribution(frame: pd.DataFrame, column: str, minimum: int) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for key, group in frame.groupby(column, dropna=False):
        metrics = _trade_metrics(group)
        records.append({column: str(key), **metrics, "sufficient_sample": len(group) >= minimum})
    return pd.DataFrame(records).sort_values(["net_pnl", "trades"], ascending=[False, False])


def _classify_regimes(frame: pd.DataFrame, window: int) -> pd.DataFrame:
    result = frame.sort_values("entry_timestamp").copy()
    stream = result["net_return"].astype(float)
    rolling_mean = (
        stream.rolling(window, min_periods=max(5, window // 5))
        .mean()
        .fillna(stream.expanding().mean())
    )
    rolling_vol = (
        stream.rolling(window, min_periods=max(5, window // 5))
        .std()
        .fillna(stream.expanding().std())
        .fillna(0.0)
    )
    vol_threshold = float(rolling_vol.median())
    trend = np.where(
        rolling_mean > 0.001, "bull", np.where(rolling_mean < -0.001, "bear", "sideways")
    )
    volatility = np.where(rolling_vol > vol_threshold, "high_volatility", "low_volatility")
    result["trend_regime"] = trend
    result["volatility_regime"] = volatility
    result["market_regime"] = (
        result["trend_regime"].astype(str) + "_" + result["volatility_regime"].astype(str)
    )
    return result


def _yearly_returns(equity: pd.DataFrame) -> pd.DataFrame:
    ordered = equity.sort_values("timestamp").copy()
    ordered["year"] = ordered["timestamp"].dt.year
    records: list[dict[str, float | int]] = []
    for year, group in ordered.groupby("year"):
        start = float(group["capital"].iloc[0])
        end = float(group["capital"].iloc[-1])
        records.append(
            {
                "year": int(str(year)),
                "starting_capital": start,
                "ending_capital": end,
                "return": end / start - 1.0 if start else 0.0,
            }
        )
    return pd.DataFrame(records)


def _rejection_attribution(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["reason", "rejections", "share"])
    frame = pd.read_csv(path)
    if frame.empty or "reason" not in frame:
        return pd.DataFrame(columns=["reason", "rejections", "share"])
    counts = frame["reason"].fillna("unknown").astype(str).value_counts()
    total = int(counts.sum())
    shares = (
        counts.to_numpy(dtype=float) / float(total) if total else np.zeros(len(counts), dtype=float)
    )
    return pd.DataFrame(
        {
            "reason": counts.index,
            "rejections": counts.to_numpy(dtype=int),
            "share": shares,
        }
    )


def run_phase14(config: Phase14Config) -> Phase14Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    trades = pd.read_csv(config.executed_trades_path)
    reported_equity = pd.read_csv(config.equity_curve_path)
    rejected_raw = (
        pd.read_csv(config.rejected_signals_path)
        if config.rejected_signals_path.exists()
        else pd.DataFrame()
    )
    required_trades = {"symbol", "entry_timestamp", "exit_timestamp", "net_return", "pnl"}
    missing = sorted(required_trades.difference(trades.columns))
    if missing:
        raise ValueError(f"executed trades are missing required columns: {missing}")
    if not {"timestamp", "capital"}.issubset(reported_equity.columns):
        raise ValueError("equity curve must contain timestamp and capital")

    trades["entry_timestamp"] = pd.to_datetime(trades["entry_timestamp"], utc=True)
    trades["exit_timestamp"] = pd.to_datetime(trades["exit_timestamp"], utc=True)
    reported_equity["timestamp"] = pd.to_datetime(reported_equity["timestamp"], utc=True)
    if not rejected_raw.empty and "entry_timestamp" in rejected_raw:
        rejected_raw["entry_timestamp"] = pd.to_datetime(rejected_raw["entry_timestamp"], utc=True)
    supplied = (
        trades["asset_class"]
        if "asset_class" in trades
        else pd.Series("unknown", index=trades.index)
    )
    trades["asset_class"] = [
        infer_asset_class(str(symbol), str(asset))
        for symbol, asset in zip(trades["symbol"], supplied, strict=True)
    ]
    regimes = _classify_regimes(trades, config.regime_window)

    reported_initial = float(reported_equity["capital"].iloc[0])
    inferred_initial = reported_initial
    if "capital_after" in trades and not trades.empty:
        inferred_initial = float(trades["capital_after"].iloc[0]) - float(trades["pnl"].iloc[0])
    realized_equity = _reconstruct_realized_equity(trades, inferred_initial)
    overall: dict[str, Any] = {
        **_annualized_metrics(realized_equity, config.risk_free_rate),
        **_trade_metrics(trades),
    }
    execution_start = pd.Timestamp(trades["entry_timestamp"].min())
    execution_end = pd.Timestamp(trades["exit_timestamp"].max())
    source_start = execution_start
    source_end = execution_end
    if not rejected_raw.empty and "entry_timestamp" in rejected_raw:
        source_start = min(source_start, pd.Timestamp(rejected_raw["entry_timestamp"].min()))
        source_end = max(source_end, pd.Timestamp(rejected_raw["entry_timestamp"].max()))
    start = source_start
    end = source_end
    overall["dataset_start"] = start.isoformat()
    overall["dataset_end"] = end.isoformat()
    overall["calendar_days"] = int((end - start).days)
    overall["execution_start"] = execution_start.isoformat()
    overall["execution_end"] = execution_end.isoformat()
    overall["execution_calendar_years"] = _years_between(execution_start, execution_end)
    source_years = _years_between(source_start, source_end)
    overall["source_calendar_years"] = source_years
    overall["execution_coverage_ratio"] = (
        _years_between(execution_start, execution_end) / source_years if source_years > 0.0 else 1.0
    )
    reported_final = float(reported_equity["capital"].iloc[-1])
    reconstructed_final = float(realized_equity["capital"].iloc[-1])
    overall["reported_equity_final_capital"] = reported_final
    overall["reconstructed_final_capital"] = reconstructed_final
    overall["equity_reconciliation_difference"] = reported_final - reconstructed_final
    overall["symbols"] = int(trades["symbol"].nunique())
    overall["asset_classes"] = int(trades["asset_class"].nunique())

    tables = {
        "asset_class_attribution": _group_attribution(
            regimes, "asset_class", config.minimum_trades_per_group
        ),
        "symbol_attribution": _group_attribution(
            regimes, "symbol", config.minimum_trades_per_group
        ),
        "regime_attribution": _group_attribution(
            regimes, "market_regime", config.minimum_trades_per_group
        ),
        "yearly_returns": _yearly_returns(realized_equity),
        "rejection_attribution": _rejection_attribution(config.rejected_signals_path),
    }
    artifact_names = {name: config.output_root / f"{name}.csv" for name in tables}
    for name, table in tables.items():
        table.to_csv(artifact_names[name], index=False)
    regimes.to_csv(config.output_root / "trade_regime_assignments.csv", index=False)

    rejection_table = tables["rejection_attribution"]
    lockout_share = 0.0
    if not rejection_table.empty:
        lockout = rejection_table.loc[
            rejection_table["reason"] == "drawdown_circuit_breaker", "share"
        ]
        lockout_share = float(lockout.iloc[0]) if not lockout.empty else 0.0
    overall["drawdown_circuit_breaker_rejection_share"] = lockout_share
    reconciliation_ok = abs(float(overall["equity_reconciliation_difference"])) <= 0.01
    coverage_ok = float(overall["execution_coverage_ratio"]) >= 0.80
    lockout_ok = lockout_share < 0.50
    diagnostics = bool(
        len(trades) > 0
        and start <= end
        and float(overall["maximum_drawdown"]) <= 1.0
        and math.isfinite(float(overall["cagr"]))
    )
    approved = bool(
        diagnostics
        and len(trades) >= config.minimum_total_trades
        and float(overall["maximum_drawdown"]) <= config.maximum_allowed_drawdown
        and reconciliation_ok
        and coverage_ok
        and lockout_ok
    )
    dashboard = {"phase": PHASE, "version": VERSION, **overall, "diagnostics_passed": diagnostics}
    signoff = {
        "phase": PHASE,
        "status": "PHASE14_RESEARCH_INTELLIGENCE_COMPLETE",
        "diagnostics_passed": diagnostics,
        "approved_for_phase15_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "notes": [
            "Performance duration and annualized metrics are explicitly reported.",
            (
                "Trade outcomes are attributed by asset class, symbol, year, "
                "and inferred market regime."
            ),
            (
                "Regime labels are descriptive diagnostics derived from the executed "
                "trade stream, not a causal market model."
            ),
            "Phase 13 reported equity is reconciled against cumulative realized trade P&L.",
            (
                "Promotion is blocked when execution coverage is low or a drawdown "
                "circuit breaker causes prolonged lockout."
            ),
            "No broker orders are submitted by Phase 14.",
        ],
    }
    artifacts = {name: str(path) for name, path in artifact_names.items()}
    artifacts.update(
        {
            "trade_regime_assignments": str(config.output_root / "trade_regime_assignments.csv"),
            "dashboard": str(config.output_root / "phase14_dashboard.json"),
            "signoff": str(config.output_root / "phase14_final_signoff.json"),
            "manifest": str(config.output_root / "manifest.json"),
        }
    )
    manifest = {
        "phase": PHASE,
        "version": VERSION,
        "config": asdict(config),
        "artifacts": artifacts,
    }
    for filename, payload in (
        ("phase14_dashboard.json", dashboard),
        ("phase14_final_signoff.json", signoff),
        ("manifest.json", manifest),
    ):
        (config.output_root / filename).write_text(json.dumps(payload, indent=2, default=str))
    return Phase14Result(
        len(trades),
        start.isoformat(),
        end.isoformat(),
        _years_between(start, end),
        diagnostics,
        approved,
        str(config.output_root),
        artifacts,
    )
