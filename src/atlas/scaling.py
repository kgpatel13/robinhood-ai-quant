from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from src.atlas.history import history_path, load_history
from src.atlas.universe import UniverseAsset


@dataclass(frozen=True)
class UniverseBatch:
    assets: tuple[UniverseAsset, ...]
    eligible_assets: int
    selected_assets: int
    offset: int
    batch_size: int | None


@dataclass(frozen=True)
class HistoryInventory:
    eligible_assets: int
    assets_with_history: int
    assets_ready_for_features: int
    missing_history: int
    insufficient_history: int
    total_bars: int
    minimum_bars: int


def prioritized_assets(registry: Sequence[UniverseAsset]) -> list[UniverseAsset]:
    active = [asset for asset in registry if asset.active and asset.tradable]
    stocks = sorted(
        (asset for asset in active if asset.asset_class == "stock"),
        key=lambda item: (item.symbol, item.asset_id),
    )
    crypto = sorted(
        (asset for asset in active if asset.asset_class == "crypto"),
        key=lambda item: (-(item.market_cap or 0.0), item.symbol, item.asset_id),
    )
    return stocks + crypto


def select_universe_batch(
    registry: Sequence[UniverseAsset],
    *,
    stock_limit: int | None,
    crypto_limit: int | None,
    offset: int = 0,
    batch_size: int | None = None,
) -> UniverseBatch:
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if batch_size is not None and batch_size <= 0:
        raise ValueError("batch_size must be positive when provided")

    prioritized = prioritized_assets(registry)
    stocks = [asset for asset in prioritized if asset.asset_class == "stock"]
    crypto = [asset for asset in prioritized if asset.asset_class == "crypto"]
    selected = stocks[:stock_limit] if stock_limit is not None else stocks
    selected += crypto[:crypto_limit] if crypto_limit is not None else crypto
    selected = selected[offset:]
    if batch_size is not None:
        selected = selected[:batch_size]
    return UniverseBatch(
        assets=tuple(selected),
        eligible_assets=len(prioritized),
        selected_assets=len(selected),
        offset=offset,
        batch_size=batch_size,
    )


def inspect_history_inventory(
    registry: Sequence[UniverseAsset],
    history_root: Path,
    *,
    minimum_bars: int = 60,
) -> HistoryInventory:
    if minimum_bars <= 0:
        raise ValueError("minimum_bars must be positive")
    eligible = prioritized_assets(registry)
    with_history = 0
    ready = 0
    insufficient = 0
    total_bars = 0
    for asset in eligible:
        path = history_path(history_root, asset)
        if not path.exists():
            continue
        bars = load_history(path)
        with_history += 1
        total_bars += len(bars)
        if len(bars) >= minimum_bars:
            ready += 1
        else:
            insufficient += 1
    return HistoryInventory(
        eligible_assets=len(eligible),
        assets_with_history=with_history,
        assets_ready_for_features=ready,
        missing_history=len(eligible) - with_history,
        insufficient_history=insufficient,
        total_bars=total_bars,
        minimum_bars=minimum_bars,
    )
