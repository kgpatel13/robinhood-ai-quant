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
from src.research.phase10.portfolio import PortfolioConfig, period_performance, simulate_portfolio
from src.research.phase10.replay import assign_score_band, replay_symbol
from src.research.phase10.robustness import (
    PromotionRules,
    benchmark_comparison,
    leakage_audit,
    promotion_decisions,
    research_signoff,
    rolling_walk_forward_validation,
    transaction_cost_stress,
    window_stability,
)
from src.research.phase10.walk_forward import fixed_split_validation
from src.research.validation import discover_datasets, validate_dataset


def _asset_class(symbol: str, config: Phase10Config) -> AssetClass:
    upper = symbol.upper()
    if upper.endswith(("-USD", "-USDC")):
        return "crypto"
    if upper in set(config.etf_symbols):
        return "etf"
    return "stock"


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


def _price_matrix(price_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series: list[pd.Series] = []
    for symbol, frame in price_frames.items():
        timestamps = pd.to_datetime(frame["timestamp"], utc=True)
        values = pd.Series(frame["close"].astype(float).to_numpy(), index=timestamps, name=symbol)
        series.append(values[~values.index.duplicated(keep="last")])
    return pd.concat(series, axis=1).sort_index() if series else pd.DataFrame()


def _portfolio_outputs(
    replay: pd.DataFrame,
    prices: pd.DataFrame,
    config: Phase10Config,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    portfolio_config = PortfolioConfig(
        initial_capital=config.portfolio_initial_capital,
        risk_per_trade=config.portfolio_risk_per_trade,
        maximum_position_percent=config.portfolio_maximum_position_percent,
        maximum_concurrent_positions=config.portfolio_maximum_concurrent_positions,
        one_position_per_symbol=config.portfolio_one_position_per_symbol,
        cooldown_bars_after_exit=config.portfolio_cooldown_bars_after_exit,
    )
    trade_frames: list[pd.DataFrame] = []
    equity_frames: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    skipped_frames: list[pd.DataFrame] = []
    for asset_class in ("stock", "etf", "crypto"):
        profile = _profile(config, asset_class)
        for holding_period in profile.holding_periods:
            scenario = {
                "asset_class": asset_class,
                "holding_period": holding_period,
                "threshold": profile.entry_score,
            }
            signals = replay[
                (replay["asset_class"] == asset_class)
                & (replay["holding_period"] == holding_period)
                & (replay["opportunity_score"] >= profile.entry_score)
            ]
            trades, equity, summary, skipped = simulate_portfolio(
                signals, prices, portfolio_config, scenario
            )
            if not trades.empty:
                trade_frames.append(trades)
            if not equity.empty:
                equity_frames.append(equity)
            summaries.append(summary)
            if not skipped.empty:
                skipped_frames.append(skipped)
    return (
        pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame(),
        pd.concat(equity_frames, ignore_index=True) if equity_frames else pd.DataFrame(),
        pd.DataFrame(summaries),
        pd.concat(skipped_frames, ignore_index=True) if skipped_frames else pd.DataFrame(),
    )


def run_phase10_replay(data_root: Path, config: Phase10Config) -> Phase10Result:
    registry = discover_datasets(data_root)
    selected = tuple(config.symbols) if config.symbols else tuple(sorted(registry))
    unknown = sorted(set(selected).difference(registry))
    if unknown:
        raise ValueError(f"Unknown symbols: {unknown}")

    replay_frames: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    price_frames: dict[str, pd.DataFrame] = {}
    for symbol in selected:
        try:
            raw = pd.read_parquet(registry[symbol])
            validation = validate_dataset(raw, registry[symbol])
            asset_class = _asset_class(symbol, config)
            profile = _profile(config, asset_class)
            if validation.rows < profile.minimum_history:
                message = f"insufficient history: {validation.rows} < {profile.minimum_history}"
                raise ValueError(message)
            price_frames[symbol] = raw[["timestamp", "close"]].copy()
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
    for asset_class in ("stock", "etf", "crypto"):
        mask = replay["asset_class"] == asset_class
        if not mask.any():
            continue
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
        "etf": config.stock_profile.minimum_trades_per_band,
        "crypto": config.crypto_profile.minimum_trades_per_band,
    }
    recommendations = threshold_recommendations(score_bands, minimum_trades)
    artifacts["threshold_recommendations"] = _write_csv(
        recommendations, output / "threshold_recommendations.csv"
    )

    prices = _price_matrix(price_frames)
    portfolio_trades, daily_equity, portfolio_summary, skipped = _portfolio_outputs(
        replay, prices, config
    )
    artifacts["portfolio_trades"] = _write_csv(portfolio_trades, output / "portfolio_trades.csv")
    artifacts["daily_equity"] = _write_csv(daily_equity, output / "daily_equity.csv")
    artifacts["portfolio_summary"] = _write_csv(portfolio_summary, output / "portfolio_summary.csv")
    artifacts["skipped_signals"] = _write_csv(skipped, output / "skipped_signals.csv")
    artifacts["year_performance"] = _write_csv(
        period_performance(daily_equity, "year"), output / "year_performance.csv"
    )
    artifacts["monthly_performance"] = _write_csv(
        period_performance(daily_equity, "month"), output / "monthly_performance.csv"
    )
    exposure_rows: list[dict[str, object]] = []
    if not daily_equity.empty:
        exposure_groups = daily_equity.groupby(
            ["asset_class", "holding_period", "threshold"], observed=True
        )
        for raw_key, group in exposure_groups:
            if not isinstance(raw_key, tuple) or len(raw_key) != 3:
                raise ValueError(f"Unexpected exposure grouping key: {raw_key!r}")
            exposure_rows.append(
                {
                    "asset_class": str(raw_key[0]),
                    "holding_period": int(str(raw_key[1])),
                    "threshold": float(str(raw_key[2])),
                    "average_exposure": float(group["exposure"].mean()),
                    "maximum_exposure": float(group["exposure"].max()),
                    "average_open_positions": float(group["open_positions"].mean()),
                    "maximum_open_positions": int(group["open_positions"].max()),
                }
            )
    exposure = pd.DataFrame(exposure_rows)
    artifacts["exposure_analysis"] = _write_csv(exposure, output / "exposure_analysis.csv")

    thresholds = {
        "stock": tuple(config.stock_profile.score_bands[:-1]),
        "etf": tuple(config.stock_profile.score_bands[:-1]),
        "crypto": tuple(config.crypto_profile.score_bands[:-1]),
    }
    walk_forward = fixed_split_validation(
        replay,
        thresholds,
        config.walk_forward_train_end_year,
        config.walk_forward_validation_end_year,
        minimum_trades,
    )
    artifacts["walk_forward_results"] = _write_csv(
        walk_forward, output / "walk_forward_results.csv"
    )

    rolling = rolling_walk_forward_validation(
        replay,
        thresholds,
        minimum_trades,
        train_years=config.rolling_train_years,
        validation_years=config.rolling_validation_years,
        test_years=config.rolling_test_years,
        step_years=config.rolling_step_years,
    )
    artifacts["rolling_walk_forward_results"] = _write_csv(
        rolling, output / "rolling_walk_forward_results.csv"
    )
    stability = window_stability(rolling)
    artifacts["window_stability"] = _write_csv(stability, output / "window_stability.csv")

    cost_stress = transaction_cost_stress(
        replay,
        {
            "stock": {"optimistic": 0.0, "base": 5.0, "stress": 10.0},
            "etf": {"optimistic": 0.0, "base": 3.0, "stress": 7.0},
            "crypto": {"optimistic": 0.0, "base": 25.0, "stress": 50.0},
        },
    )
    artifacts["transaction_cost_stress"] = _write_csv(
        cost_stress, output / "transaction_cost_stress.csv"
    )
    benchmark = benchmark_comparison(
        daily_equity, prices, {"stock": "SPY", "etf": "SPY", "crypto": "BTC-USD"}
    )
    artifacts["benchmark_comparison"] = _write_csv(benchmark, output / "benchmark_comparison.csv")
    leakage = leakage_audit(replay)
    artifacts["leakage_audit"] = _write_csv(leakage, output / "leakage_audit.csv")
    decisions = promotion_decisions(
        stability,
        PromotionRules(
            minimum_profitable_window_fraction=config.promotion_minimum_profitable_window_fraction,
            minimum_median_profit_factor=config.promotion_minimum_median_profit_factor,
            minimum_test_trades=config.promotion_minimum_test_trades,
            maximum_threshold_range=config.promotion_maximum_threshold_range,
        ),
    )
    artifacts["promotion_decisions"] = _write_csv(decisions, output / "promotion_decisions.csv")
    data_cutoff = str(pd.to_datetime(replay["signal_timestamp"], utc=True).max())
    signoff = research_signoff(decisions, leakage, "0.10.2", data_cutoff)
    signoff_path = output / "phase10_research_signoff.json"
    signoff_path.write_text(json.dumps(signoff, indent=2), encoding="utf-8")
    artifacts["research_signoff"] = str(signoff_path)

    failures_path = output / "replay_failures.json"
    failures_path.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    artifacts["failures"] = str(failures_path)

    primary = threshold[threshold["holding_period"] == config.primary_holding_period].to_dict(
        orient="records"
    )
    manifest = {
        "phase": "10.2.0",
        "mode": "robustness_validated_historical_signal_replay",
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
            "Each holding period is simulated as an independent portfolio scenario.",
            "Portfolio drawdown is calculated from chronological marked-to-market equity.",
            "Overlapping positions, capacity limits, and cooldowns are enforced.",
            "Threshold recommendations remain research candidates until "
            "rolling out-of-sample review."
            "Promotion decisions require rolling-window stability and a clean leakage audit.",
            "Transaction-cost stress and benchmark comparison are included in sign-off.",
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
