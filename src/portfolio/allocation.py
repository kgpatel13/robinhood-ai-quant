from __future__ import annotations

import math

import pandas as pd


def normalize_weights(weights: dict[str, float], max_asset_weight: float = 1.0) -> dict[str, float]:
    if any(value < 0 for value in weights.values()):
        raise ValueError("weights cannot be negative")
    positive = {symbol: float(value) for symbol, value in weights.items() if value > 0}
    if not positive:
        return {symbol: 0.0 for symbol in weights}
    total = sum(positive.values())
    normalized = {symbol: value / total for symbol, value in positive.items()}
    if max_asset_weight >= 1.0:
        return {symbol: normalized.get(symbol, 0.0) for symbol in weights}

    capped = {symbol: 0.0 for symbol in normalized}
    remaining = 1.0
    active = set(normalized)
    while active and remaining > 1e-12:
        active_total = sum(normalized[symbol] for symbol in active)
        if active_total <= 0:
            break
        changed = False
        for symbol in list(active):
            proposed = remaining * normalized[symbol] / active_total
            if proposed >= max_asset_weight:
                capped[symbol] += max_asset_weight
                remaining -= max_asset_weight
                active.remove(symbol)
                changed = True
        if not changed:
            for symbol in active:
                capped[symbol] += remaining * normalized[symbol] / active_total
            remaining = 0.0
    return {symbol: capped.get(symbol, 0.0) for symbol in weights}


def equal_weights(symbols: list[str], max_asset_weight: float = 1.0) -> dict[str, float]:
    if not symbols:
        return {}
    return normalize_weights({symbol: 1.0 for symbol in symbols}, max_asset_weight)


def fixed_weights(
    symbols: list[str], configured: dict[str, float], max_asset_weight: float = 1.0
) -> dict[str, float]:
    missing = sorted(set(symbols) - set(configured))
    unknown = sorted(set(configured) - set(symbols))
    if missing:
        raise ValueError(f"Missing fixed weights for: {missing}")
    if unknown:
        raise ValueError(f"Fixed weights contain unknown symbols: {unknown}")
    return normalize_weights({symbol: configured[symbol] for symbol in symbols}, max_asset_weight)


def inverse_volatility_weights(
    returns: pd.DataFrame, symbols: list[str], max_asset_weight: float = 1.0
) -> dict[str, float]:
    raw: dict[str, float] = {}
    for symbol in symbols:
        values = returns[symbol].dropna() if symbol in returns else pd.Series(dtype=float)
        volatility = float(values.std(ddof=0)) if len(values) >= 2 else math.nan
        raw[symbol] = 0.0 if not math.isfinite(volatility) or volatility <= 0 else 1.0 / volatility
    if not any(value > 0 for value in raw.values()):
        return equal_weights(symbols, max_asset_weight)
    return normalize_weights(raw, max_asset_weight)
