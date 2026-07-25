from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase10.analytics import (
    aggregate,
    score_monotonicity,
    threshold_recommendations,
)
from src.research.phase10.features import build_feature_frame
from src.research.phase10.models import (
    AssetClass,
    Phase10Config,
    Phase10Result,
    ReplayProfile,
)
from src.research.phase10.replay import assign_score_band, replay_symbol
from src.research.validation import discover_datasets, validate_dataset


def _asset_class(symbol: str) -> AssetClass:
    return "crypto" if symbol.upper().endswith(("-USD", "-USDC")) else "stock"


def _profile(config: Phase10Config, asset_class: AssetClass) -> ReplayProfile:
    return config.crypto_profile if asset_class == "crypto" else config.stock_profile


def _write_csv(frame: pd.DataFrame, path: Path) -> str:
    frame.to_csv(path, index=False)
    return str(path)


def _band_lower_mapping(profile: ReplayProfile) -> dict[str, float]:
    return {
        f"{profile.score_bands[index]:g}-{profile.score_bands[index + 1]:g}": (
            profile.score_bands[index]
        )
        for index in range(len(profile.score_bands) - 1)
    }


def run_phase10_replay(data_root: Path, config: Phase10Config) -> Phase10Result:
    registry = discover_datasets(data_root)
    selected = tuple(config.symbols) if config.symbols else tuple(sorted(registry))
    unknown = sorted(set(selected).difference(registry))
    if unknown:
        raise ValueError(f"Unknown symbols: {unknown}")

    replay_frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    for symbol in selected:
        try:
            raw = pd.read_parquet(registry[symbol])
            validation = validate_dataset(raw, registry[symbol])
            asset_class = _asset_class(symbol)
            profile = _profile(config, asset_class)
            if validation.rows < profile.minimum_history:
                message = f"insufficient history: {validation.rows} < {profile.minimum_history}"
                raise ValueError(message)
            replay = replay_symbol(
                build_feature_frame(raw),
                asset_class,
                profile,
                config.warmup_bars,
                config.signal_stride,
                config.same_bar_policy,
                config.include_below_threshold,
            )
            replay_frames.append(replay)
        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    if not replay_frames or all(frame.empty for frame in replay_frames):
        raise RuntimeError("No historical signals were replayed")
    replay = pd.concat(replay_frames, ignore_index=True)
    replay["score_band"] = pd.Series("", index=replay.index, dtype="object")
    replay["band_lower"] = 0.0
    for asset_class in ("stock", "crypto"):
        mask = replay["asset_class"] == asset_class
        profile = _profile(config, asset_class)
        bands = assign_score_band(replay.loc[mask, "opportunity_score"], profile.score_bands)
        band_strings = bands.astype("string")
        replay.loc[mask, "score_band"] = band_strings.astype(object)
        mapping = _band_lower_mapping(profile)
        replay.loc[mask, "band_lower"] = band_strings.map(mapping).astype(float)

    output = config.output_root
    output.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    artifacts["signal_replay"] = _write_csv(replay, output / "signal_replay.csv")
    score_bands = aggregate(
        replay,
        ["asset_class", "holding_period", "score_band", "band_lower"],
    )
    artifacts["score_band_performance"] = _write_csv(
        score_bands, output / "score_band_performance.csv"
    )
    threshold = aggregate(replay[replay["eligible"]], ["asset_class", "holding_period"])
    artifacts["threshold_performance"] = _write_csv(threshold, output / "threshold_performance.csv")
    symbols = aggregate(replay, ["symbol", "asset_class", "holding_period", "eligible"])
    artifacts["symbol_performance"] = _write_csv(symbols, output / "symbol_performance.csv")
    regimes = aggregate(replay, ["asset_class", "holding_period", "regime", "eligible"])
    artifacts["regime_performance"] = _write_csv(regimes, output / "regime_performance.csv")
    monotonicity = score_monotonicity(score_bands)
    artifacts["score_monotonicity"] = _write_csv(monotonicity, output / "score_monotonicity.csv")
    minimum_trades = {
        "stock": config.stock_profile.minimum_trades_per_band,
        "crypto": config.crypto_profile.minimum_trades_per_band,
    }
    recommendations = threshold_recommendations(score_bands, minimum_trades)
    artifacts["threshold_recommendations"] = _write_csv(
        recommendations, output / "threshold_recommendations.csv"
    )
    failures_path = output / "replay_failures.json"
    failures_path.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    artifacts["failures"] = str(failures_path)

    primary = threshold[threshold["holding_period"] == config.primary_holding_period].to_dict(
        orient="records"
    )
    manifest = {
        "phase": "10.0.0",
        "mode": "historical_signal_replay",
        "config": asdict(config),
        "scanned_symbols": len(selected) - len(failures),
        "failed_symbols": len(failures),
        "replayed_signals": len(replay),
        "threshold_signals": int(replay["eligible"].sum()),
        "primary_holding_period": config.primary_holding_period,
        "primary_threshold_performance": primary,
        "research_controls": [
            "Signals use only information available at the signal close.",
            "Entry occurs at the next bar open to prevent look-ahead bias.",
            "Stop/target conflicts use the configured same-bar policy.",
            "Returns include spread, slippage, and fee assumptions.",
            (
                "Threshold recommendations are research candidates, "
                "not automatic production changes."
            ),
        ],
        "artifacts": artifacts,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    artifacts["manifest"] = str(manifest_path)
    return Phase10Result(
        scanned_symbols=len(selected) - len(failures),
        replayed_signals=len(replay),
        threshold_signals=int(replay["eligible"].sum()),
        output=str(output),
        artifacts=artifacts,
    )
