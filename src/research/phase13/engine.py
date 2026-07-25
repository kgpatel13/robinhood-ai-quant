from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Protocol, cast

import pandas as pd

from src.research.phase13.models import Phase13Config, Phase13Result

PHASE = "13.0-13.9"
VERSION = "0.13.0"


class _CandidateRow(Protocol):
    symbol: object
    asset_class: object
    entry_timestamp: object
    exit_timestamp: object
    probability: object
    volatility: object
    net_return: object


@dataclass(frozen=True)
class _CandidateTrade:
    symbol: str
    asset_class: str
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    probability: float
    volatility: float
    net_return: float


@dataclass(frozen=True)
class _OpenPosition:
    symbol: str
    asset_class: str
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    probability: float
    volatility: float
    position_fraction: float
    allocated_capital: float
    gross_return: float
    net_return: float


def _as_float(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    if isinstance(value, (int, float, str)):
        return float(value)
    raise ValueError(f"{field} must be numeric")


def _as_timestamp(value: object, *, field: str) -> pd.Timestamp:
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, (str, date, datetime)):
        return pd.Timestamp(value)
    raise ValueError(f"{field} must be timestamp-compatible")


def confidence_multiplier(probability: float, config: Phase13Config) -> float:
    clipped = min(max(probability, config.confidence_floor), config.confidence_ceiling)
    span = config.confidence_ceiling - config.confidence_floor
    return 0.5 + 0.5 * ((clipped - config.confidence_floor) / span)


def volatility_position_fraction(
    probability: float, volatility: float, config: Phase13Config
) -> float:
    safe_volatility = min(max(abs(volatility), config.volatility_floor), config.volatility_ceiling)
    risk_fraction = config.target_risk_per_trade / safe_volatility
    fraction = risk_fraction * confidence_multiplier(probability, config)
    return float(min(max(fraction, 0.0), config.maximum_position_fraction))


def _normalize_trades(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "entry_timestamp" not in result and "timestamp" in result:
        result["entry_timestamp"] = result["timestamp"]
    if "net_return" not in result and "net_return_after_costs" in result:
        result["net_return"] = result["net_return_after_costs"]
    required = {"symbol", "entry_timestamp", "net_return"}
    missing = sorted(required.difference(result.columns))
    if missing:
        raise ValueError(f"trade input is missing required columns: {missing}")
    result["entry_timestamp"] = pd.to_datetime(result["entry_timestamp"], utc=True)
    if "exit_timestamp" not in result:
        if "holding_period" in result:
            holding = pd.to_numeric(result["holding_period"], errors="coerce").fillna(1)
        else:
            holding = pd.Series(1, index=result.index, dtype="int64")
        result["exit_timestamp"] = result["entry_timestamp"] + pd.to_timedelta(
            holding, unit="D"
        )
    result["exit_timestamp"] = pd.to_datetime(result["exit_timestamp"], utc=True)
    result["net_return"] = pd.to_numeric(result["net_return"], errors="coerce")
    if "probability" not in result:
        result["probability"] = 0.60
    if "asset_class" not in result:
        result["asset_class"] = "unknown"
    if "volatility" not in result:
        result["volatility"] = result["net_return"].abs().rolling(20, min_periods=2).std()
    result["volatility"] = pd.to_numeric(result["volatility"], errors="coerce").fillna(0.02)
    return result.dropna(subset=["entry_timestamp", "exit_timestamp", "net_return"]).sort_values(
        ["entry_timestamp", "probability"], ascending=[True, False]
    )


def _candidate_from_row(row: object) -> _CandidateTrade:
    typed_row = cast(_CandidateRow, row)
    return _CandidateTrade(
        symbol=str(typed_row.symbol),
        asset_class=str(typed_row.asset_class),
        entry_timestamp=_as_timestamp(
            typed_row.entry_timestamp, field="entry_timestamp"
        ),
        exit_timestamp=_as_timestamp(
            typed_row.exit_timestamp, field="exit_timestamp"
        ),
        probability=_as_float(typed_row.probability, field="probability"),
        volatility=_as_float(typed_row.volatility, field="volatility"),
        net_return=_as_float(typed_row.net_return, field="net_return"),
    )


def _position_record(position: _OpenPosition) -> dict[str, object]:
    return {
        "symbol": position.symbol,
        "asset_class": position.asset_class,
        "entry_timestamp": position.entry_timestamp,
        "exit_timestamp": position.exit_timestamp,
        "probability": position.probability,
        "volatility": position.volatility,
        "position_fraction": position.position_fraction,
        "allocated_capital": position.allocated_capital,
        "gross_return": position.gross_return,
        "net_return": position.net_return,
    }


def simulate_portfolio(
    trades: pd.DataFrame, config: Phase13Config
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float | int]]:
    candidates = _normalize_trades(trades)
    capital = config.initial_capital
    peak = capital
    halted = False
    open_positions: list[_OpenPosition] = []
    executed: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []
    day_start_capital = capital
    current_day: date | None = None
    cost_rate = (config.slippage_bps + config.commission_bps) / 10_000.0

    for raw_row in candidates.itertuples(index=False):
        row = _candidate_from_row(raw_row)
        entry = row.entry_timestamp
        day = entry.date()
        if day != current_day:
            current_day = day
            day_start_capital = capital

        still_open: list[_OpenPosition] = []
        for position in open_positions:
            if position.exit_timestamp <= entry:
                pnl = position.allocated_capital * position.net_return
                capital += pnl
                executed.append(
                    {**_position_record(position), "pnl": pnl, "capital_after": capital}
                )
            else:
                still_open.append(position)
        open_positions = still_open
        peak = max(peak, capital)
        drawdown = 1.0 - capital / peak if peak else 0.0
        if halted and drawdown <= config.recovery_drawdown:
            halted = False
        if drawdown >= config.portfolio_drawdown_limit:
            halted = True

        reason = ""
        probability = row.probability
        asset_class = row.asset_class
        symbol = row.symbol
        daily_return = capital / day_start_capital - 1.0 if day_start_capital else 0.0
        gross_exposure = (
            sum(position.allocated_capital for position in open_positions) / capital
            if capital > 0.0
            else 0.0
        )
        asset_exposure = (
            sum(
                position.allocated_capital
                for position in open_positions
                if position.asset_class == asset_class
            )
            / capital
            if capital > 0.0
            else 0.0
        )

        if halted:
            reason = "drawdown_circuit_breaker"
        elif daily_return <= -config.daily_loss_limit:
            reason = "daily_loss_limit"
        elif probability < config.confidence_floor:
            reason = "confidence_floor"
        elif len(open_positions) >= config.maximum_open_positions:
            reason = "position_limit"
        elif any(position.symbol == symbol for position in open_positions):
            reason = "symbol_overlap"
        elif gross_exposure >= config.maximum_gross_exposure:
            reason = "gross_exposure_limit"
        elif asset_exposure >= config.maximum_asset_class_exposure:
            reason = "asset_class_exposure_limit"

        fraction = volatility_position_fraction(probability, row.volatility, config)
        fraction = min(
            fraction,
            max(config.maximum_gross_exposure - gross_exposure, 0.0),
            max(config.maximum_asset_class_exposure - asset_exposure, 0.0),
        )
        if not reason and fraction <= 0.0:
            reason = "no_available_exposure"
        if reason:
            rejected.append(
                {
                    "symbol": symbol,
                    "entry_timestamp": entry,
                    "reason": reason,
                    "probability": probability,
                }
            )
            continue

        allocated = capital * fraction
        net_return = row.net_return - 2.0 * cost_rate
        open_positions.append(
            _OpenPosition(
                symbol=symbol,
                asset_class=asset_class,
                entry_timestamp=entry,
                exit_timestamp=row.exit_timestamp,
                probability=probability,
                volatility=row.volatility,
                position_fraction=fraction,
                allocated_capital=allocated,
                gross_return=row.net_return,
                net_return=net_return,
            )
        )
        equity_rows.append(
            {
                "timestamp": entry,
                "capital": capital,
                "open_positions": len(open_positions),
                "gross_exposure": (
                    sum(position.allocated_capital for position in open_positions) / capital
                    if capital > 0.0
                    else 0.0
                ),
                "drawdown": drawdown,
                "halted": halted,
            }
        )

    for position in sorted(open_positions, key=lambda item: item.exit_timestamp):
        pnl = position.allocated_capital * position.net_return
        capital += pnl
        executed.append({**_position_record(position), "pnl": pnl, "capital_after": capital})
        peak = max(peak, capital)
        equity_rows.append(
            {
                "timestamp": position.exit_timestamp,
                "capital": capital,
                "open_positions": 0,
                "gross_exposure": 0.0,
                "drawdown": 1.0 - capital / peak if peak else 0.0,
                "halted": halted,
            }
        )

    executed_frame = pd.DataFrame(executed)
    rejected_frame = pd.DataFrame(rejected)
    equity = pd.DataFrame(equity_rows).sort_values("timestamp") if equity_rows else pd.DataFrame()
    maximum_drawdown = float(equity["drawdown"].max()) if not equity.empty else 0.0
    wins = int((executed_frame["pnl"] > 0).sum()) if not executed_frame.empty else 0
    metrics: dict[str, float | int] = {
        "initial_capital": config.initial_capital,
        "final_capital": capital,
        "total_return": capital / config.initial_capital - 1.0,
        "maximum_drawdown": maximum_drawdown,
        "executed_trades": len(executed_frame),
        "rejected_trades": len(rejected_frame),
        "win_rate": wins / len(executed_frame) if len(executed_frame) else 0.0,
    }
    return executed_frame, rejected_frame, equity, metrics


def run_phase13(config: Phase13Config) -> Phase13Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(config.trades_path)
    executed, rejected, equity, metrics = simulate_portfolio(source, config)
    diagnostics = bool(
        metrics["executed_trades"] >= 0
        and 0.0 <= float(metrics["maximum_drawdown"]) <= 1.0
        and float(metrics["final_capital"]) >= 0.0
    )
    approved = bool(
        diagnostics
        and int(metrics["executed_trades"]) >= config.minimum_trades
        and float(metrics["maximum_drawdown"]) <= config.maximum_allowed_drawdown
    )
    artifacts = {
        "executed_trades": str(config.output_root / "executed_trades.csv"),
        "rejected_signals": str(config.output_root / "rejected_signals.csv"),
        "equity_curve": str(config.output_root / "portfolio_equity_curve.csv"),
        "risk_summary": str(config.output_root / "risk_summary.json"),
        "dashboard": str(config.output_root / "phase13_dashboard.json"),
        "signoff": str(config.output_root / "phase13_final_signoff.json"),
        "manifest": str(config.output_root / "manifest.json"),
    }
    executed.to_csv(artifacts["executed_trades"], index=False)
    rejected.to_csv(artifacts["rejected_signals"], index=False)
    equity.to_csv(artifacts["equity_curve"], index=False)
    (config.output_root / "risk_summary.json").write_text(json.dumps(metrics, indent=2))
    dashboard = {
        "phase": PHASE,
        "version": VERSION,
        "source_trades": len(source),
        **metrics,
        "diagnostics_passed": diagnostics,
    }
    signoff = {
        "phase": PHASE,
        "status": "PHASE13_PORTFOLIO_ENGINE_COMPLETE",
        "diagnostics_passed": diagnostics,
        "approved_for_phase14_review": approved,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
        "notes": [
            "Volatility- and confidence-adjusted position sizing is applied.",
            "Gross, asset-class, symbol-overlap, and concurrent-position limits are enforced.",
            "Daily-loss and portfolio-drawdown circuit breakers are enforced.",
            "No broker orders are submitted by Phase 13.",
        ],
    }
    manifest = {"phase": PHASE, "version": VERSION, "config": asdict(config), "artifacts": artifacts}
    for filename, payload in (
        ("phase13_dashboard.json", dashboard),
        ("phase13_final_signoff.json", signoff),
        ("manifest.json", manifest),
    ):
        (config.output_root / filename).write_text(json.dumps(payload, indent=2, default=str))
    return Phase13Result(
        source_trades=len(source),
        executed_trades=len(executed),
        rejected_trades=len(rejected),
        diagnostics_passed=diagnostics,
        approved_for_phase14_review=approved,
        output=str(config.output_root),
        artifacts=artifacts,
    )
