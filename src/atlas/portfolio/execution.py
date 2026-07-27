from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.atlas.portfolio.core import PortfolioCandidate, finite_number


@dataclass(frozen=True)
class ExecutionConfig:
    spread_bps_stock: float = 8.0
    spread_bps_crypto: float = 20.0
    base_slippage_bps: float = 3.0
    volatility_slippage_multiplier: float = 12.0
    market_impact_coefficient: float = 35.0
    maximum_participation_rate: float = 0.05
    minimum_fill_ratio: float = 0.10
    commission_per_order: float = 0.0
    regulatory_fee_bps_sell: float = 0.03
    minimum_order_value: float = 5.0
    fallback_daily_dollar_volume: float = 1_000_000.0
    execution_horizon_days: int = 1

    def __post_init__(self) -> None:
        non_negative = (
            "spread_bps_stock",
            "spread_bps_crypto",
            "base_slippage_bps",
            "volatility_slippage_multiplier",
            "market_impact_coefficient",
            "commission_per_order",
            "regulatory_fee_bps_sell",
            "minimum_order_value",
            "fallback_daily_dollar_volume",
        )
        for name in non_negative:
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if not 0.0 < self.maximum_participation_rate <= 1.0:
            raise ValueError("maximum_participation_rate must be within (0, 1]")
        if not 0.0 <= self.minimum_fill_ratio <= 1.0:
            raise ValueError("minimum_fill_ratio must be within [0, 1]")
        if self.execution_horizon_days < 1:
            raise ValueError("execution_horizon_days must be positive")


@dataclass(frozen=True)
class ExecutionOrder:
    asset_id: str
    symbol: str
    asset_class: str
    side: str
    requested_value: float
    reference_price: float
    annual_volatility: float
    daily_dollar_volume: float


@dataclass(frozen=True)
class ExecutionFill:
    asset_id: str
    symbol: str
    asset_class: str
    side: str
    requested_value: float
    filled_value: float
    unfilled_value: float
    fill_ratio: float
    reference_price: float
    execution_price: float
    requested_quantity: float
    filled_quantity: float
    spread_cost: float
    slippage_cost: float
    market_impact_cost: float
    commission_cost: float
    regulatory_fee: float
    total_cost: float
    effective_cost_bps: float
    participation_rate: float
    status: str


@dataclass(frozen=True)
class ExecutionResult:
    fills: tuple[ExecutionFill, ...]
    summary: Mapping[str, float | int | bool]
    capacity: Mapping[str, float | int]
    diagnostics: Mapping[str, Any]


def _spread_bps(asset_class: str, config: ExecutionConfig) -> float:
    return config.spread_bps_crypto if asset_class.lower() == "crypto" else config.spread_bps_stock


def _fill_ratio(order: ExecutionOrder, config: ExecutionConfig) -> tuple[float, float]:
    capacity = (
        order.daily_dollar_volume
        * config.maximum_participation_rate
        * config.execution_horizon_days
    )
    ratio = min(1.0, capacity / max(order.requested_value, 1e-12))
    if ratio < config.minimum_fill_ratio:
        return 0.0, capacity
    return ratio, capacity


def simulate_order(order: ExecutionOrder, config: ExecutionConfig) -> ExecutionFill:
    side = order.side.lower()
    if side not in {"buy", "sell"}:
        raise ValueError(f"Unsupported side: {order.side}")
    if order.requested_value < 0.0:
        raise ValueError("requested_value must be non-negative")
    if order.reference_price <= 0.0:
        raise ValueError("reference_price must be positive")
    if order.daily_dollar_volume <= 0.0:
        raise ValueError("daily_dollar_volume must be positive")

    if order.requested_value < config.minimum_order_value:
        return ExecutionFill(
            asset_id=order.asset_id,
            symbol=order.symbol,
            asset_class=order.asset_class,
            side=side,
            requested_value=order.requested_value,
            filled_value=0.0,
            unfilled_value=order.requested_value,
            fill_ratio=0.0,
            reference_price=order.reference_price,
            execution_price=order.reference_price,
            requested_quantity=order.requested_value / order.reference_price,
            filled_quantity=0.0,
            spread_cost=0.0,
            slippage_cost=0.0,
            market_impact_cost=0.0,
            commission_cost=0.0,
            regulatory_fee=0.0,
            total_cost=0.0,
            effective_cost_bps=0.0,
            participation_rate=0.0,
            status="below_minimum_order_value",
        )

    fill_ratio, capacity = _fill_ratio(order, config)
    filled_value = order.requested_value * fill_ratio
    participation = filled_value / max(
        order.daily_dollar_volume * config.execution_horizon_days,
        1e-12,
    )
    half_spread_bps = 0.5 * _spread_bps(order.asset_class, config)
    daily_volatility = max(order.annual_volatility, 0.0) / math.sqrt(252.0)
    slippage_bps = (
        config.base_slippage_bps + config.volatility_slippage_multiplier * daily_volatility * 100.0
    )
    impact_bps = config.market_impact_coefficient * math.sqrt(max(participation, 0.0))
    spread_cost = filled_value * half_spread_bps / 10_000.0
    slippage_cost = filled_value * slippage_bps / 10_000.0
    market_impact_cost = filled_value * impact_bps / 10_000.0
    commission = config.commission_per_order if filled_value > 0.0 else 0.0
    regulatory_fee = (
        filled_value * config.regulatory_fee_bps_sell / 10_000.0 if side == "sell" else 0.0
    )
    total_cost = spread_cost + slippage_cost + market_impact_cost + commission + regulatory_fee
    effective_cost_bps = total_cost / filled_value * 10_000.0 if filled_value else 0.0
    direction = 1.0 if side == "buy" else -1.0
    execution_price = order.reference_price * (1.0 + direction * effective_cost_bps / 10_000.0)
    requested_quantity = order.requested_value / order.reference_price
    filled_quantity = filled_value / execution_price if execution_price > 0.0 else 0.0
    if filled_value <= 0.0:
        status = "unfilled_capacity_limit"
    elif fill_ratio < 1.0:
        status = "partial_fill"
    else:
        status = "filled"
    return ExecutionFill(
        asset_id=order.asset_id,
        symbol=order.symbol,
        asset_class=order.asset_class,
        side=side,
        requested_value=order.requested_value,
        filled_value=filled_value,
        unfilled_value=max(order.requested_value - filled_value, 0.0),
        fill_ratio=fill_ratio,
        reference_price=order.reference_price,
        execution_price=execution_price,
        requested_quantity=requested_quantity,
        filled_quantity=filled_quantity,
        spread_cost=spread_cost,
        slippage_cost=slippage_cost,
        market_impact_cost=market_impact_cost,
        commission_cost=commission,
        regulatory_fee=regulatory_fee,
        total_cost=total_cost,
        effective_cost_bps=effective_cost_bps,
        participation_rate=participation,
        status=status,
    )


def build_orders_from_weights(
    target_weights: Mapping[str, float],
    candidates: Sequence[PortfolioCandidate],
    capital: float,
    current_weights: Mapping[str, float] | None = None,
    daily_dollar_volume: Mapping[str, float] | None = None,
    fallback_daily_dollar_volume: float = 1_000_000.0,
) -> tuple[ExecutionOrder, ...]:
    if capital <= 0.0:
        raise ValueError("capital must be positive")
    current = current_weights or {}
    volume = daily_dollar_volume or {}
    by_id = {item.asset_id: item for item in candidates}
    asset_ids = sorted(set(target_weights) | set(current))
    orders: list[ExecutionOrder] = []
    for asset_id in asset_ids:
        candidate = by_id.get(asset_id)
        if candidate is None:
            continue
        change = float(target_weights.get(asset_id, 0.0)) - float(current.get(asset_id, 0.0))
        requested_value = abs(change) * capital
        if requested_value <= 0.0:
            continue
        price = finite_number(candidate.price) or 0.0
        if price <= 0.0:
            continue
        volatility = finite_number(candidate.volatility_60d) or 0.25
        adv = finite_number(volume.get(asset_id)) or fallback_daily_dollar_volume
        orders.append(
            ExecutionOrder(
                asset_id=asset_id,
                symbol=candidate.symbol,
                asset_class=candidate.asset_class,
                side="buy" if change > 0.0 else "sell",
                requested_value=requested_value,
                reference_price=price,
                annual_volatility=max(volatility, 0.0),
                daily_dollar_volume=max(adv, 1.0),
            )
        )
    return tuple(orders)


def simulate_execution(
    orders: Sequence[ExecutionOrder],
    config: ExecutionConfig | None = None,
) -> ExecutionResult:
    cfg = config or ExecutionConfig()
    fills = tuple(simulate_order(order, cfg) for order in orders)
    requested = sum(item.requested_value for item in fills)
    filled = sum(item.filled_value for item in fills)
    total_cost = sum(item.total_cost for item in fills)
    fill_ratio = filled / requested if requested else 1.0
    capacity_values = [
        item.daily_dollar_volume * cfg.maximum_participation_rate * cfg.execution_horizon_days
        for item in orders
    ]
    deployable = sum(capacity_values)
    summary: dict[str, float | int | bool] = {
        "order_count": len(fills),
        "filled_order_count": sum(item.status == "filled" for item in fills),
        "partial_fill_count": sum(item.status == "partial_fill" for item in fills),
        "unfilled_order_count": sum(item.filled_value == 0.0 for item in fills),
        "requested_value": requested,
        "filled_value": filled,
        "unfilled_value": max(requested - filled, 0.0),
        "aggregate_fill_ratio": fill_ratio,
        "total_execution_cost": total_cost,
        "effective_cost_bps": total_cost / filled * 10_000.0 if filled else 0.0,
        "all_orders_filled": all(item.status == "filled" for item in fills),
    }
    capacity: dict[str, float | int] = {
        "execution_horizon_days": cfg.execution_horizon_days,
        "maximum_participation_rate": cfg.maximum_participation_rate,
        "aggregate_daily_deployable_value": deployable,
        "largest_single_order_capacity": max(capacity_values, default=0.0),
        "smallest_single_order_capacity": min(capacity_values, default=0.0),
    }
    diagnostics: dict[str, Any] = {
        "paper_only": True,
        "model": "deterministic_spread_slippage_square_root_impact",
        "assumptions": asdict(cfg),
        "warnings": [
            "Quoted bid/ask data is not available; spread is modeled from asset class.",
            (
                "Daily dollar volume may use a configured fallback where point-in-time "
                "volume is unavailable."
            ),
            "This is an execution-cost simulator, not a broker fill guarantee.",
        ],
    }
    return ExecutionResult(
        fills=fills,
        summary=summary,
        capacity=capacity,
        diagnostics=diagnostics,
    )


def load_daily_dollar_volume(history_directory: Path, asset_ids: Sequence[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for asset_id in asset_ids:
        path = history_directory / f"{asset_id.replace(':', '__')}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        columns = {str(column).lower(): str(column) for column in frame.columns}
        close_col = columns.get("close") or columns.get("adj_close")
        volume_col = columns.get("volume")
        if close_col is None or volume_col is None:
            continue
        close = pd.to_numeric(frame[close_col], errors="coerce")
        volume = pd.to_numeric(frame[volume_col], errors="coerce")
        dollar_volume = (close * volume).dropna().tail(20)
        if not dollar_volume.empty:
            result[asset_id] = float(dollar_volume.median())
    return result


def write_execution_reports(result: ExecutionResult, output_directory: Path) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    fills_path = output_directory / "execution_fills.csv"
    pd.DataFrame([asdict(item) for item in result.fills]).to_csv(fills_path, index=False)
    payloads: dict[str, Any] = {
        "execution_summary.json": dict(result.summary),
        "execution_capacity.json": dict(result.capacity),
        "execution_diagnostics.json": dict(result.diagnostics),
    }
    artifacts = {"execution_fills": str(fills_path)}
    for filename, payload in payloads.items():
        path = output_directory / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        artifacts[path.stem] = str(path)
    return artifacts
