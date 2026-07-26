from __future__ import annotations

import math

from src.atlas.models import MarketSnapshot, OpportunityScore, StrategyName


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def detect_regime(snapshot: MarketSnapshot) -> str:
    if snapshot.volatility_20d >= 0.055:
        return "high_volatility"
    if snapshot.return_20d >= 0.08 and snapshot.return_5d > 0:
        return "bull_trend"
    if snapshot.return_20d <= -0.08 and snapshot.return_5d < 0:
        return "bear_trend"
    if abs(snapshot.return_20d) < 0.03:
        return "range_bound"
    return "mixed"


def select_strategy(snapshot: MarketSnapshot, regime: str) -> StrategyName:
    if snapshot.spread_bps > 35 or snapshot.relative_volume < 0.55:
        return "cash"
    if regime in {"bull_trend", "bear_trend"} and abs(snapshot.return_5d) >= 0.025:
        return "momentum_swing"
    if regime == "range_bound" and snapshot.distance_from_20d_high <= -0.08:
        return "mean_reversion"
    if snapshot.relative_volume >= 1.8 and abs(snapshot.return_1d) >= 0.02:
        return "intraday_momentum"
    return "cash"


def score_opportunity(snapshot: MarketSnapshot) -> OpportunityScore:
    regime = detect_regime(snapshot)
    strategy = select_strategy(snapshot, regime)

    momentum = _clip(0.5 + 2.5 * snapshot.return_5d + snapshot.return_20d)
    reversal = _clip(abs(min(snapshot.distance_from_20d_high, 0.0)) / 0.20)
    liquidity = _clip(math.log10(max(snapshot.average_daily_volume * snapshot.price, 1.0)) / 9.0)
    volume = _clip(snapshot.relative_volume / 3.0)
    volatility_fit = _clip(1.0 - abs(snapshot.volatility_20d - 0.03) / 0.06)
    execution = _clip(1.0 - snapshot.spread_bps / 50.0)
    regime_fit = {
        "bull_trend": momentum,
        "bear_trend": momentum,
        "range_bound": reversal,
        "high_volatility": volatility_fit * 0.7,
        "mixed": 0.5,
    }[regime]

    strategy_signal = {
        "momentum_swing": momentum,
        "mean_reversion": reversal,
        "intraday_momentum": (momentum + volume) / 2.0,
        "cash": 0.0,
    }[strategy]

    components = {
        "strategy_signal": strategy_signal,
        "regime_fit": regime_fit,
        "liquidity": liquidity,
        "relative_volume": volume,
        "volatility_fit": volatility_fit,
        "execution_quality": execution,
    }
    weighted = (
        0.35 * strategy_signal
        + 0.15 * regime_fit
        + 0.15 * liquidity
        + 0.15 * volume
        + 0.10 * volatility_fit
        + 0.10 * execution
    )
    alpha_score = 0.0 if strategy == "cash" else round(100.0 * weighted, 4)
    confidence = round(100.0 * _clip(0.65 * weighted + 0.35 * min(liquidity, execution)), 4)
    hold = {"intraday_momentum": 1, "mean_reversion": 3, "momentum_swing": 5, "cash": 0}[strategy]

    explanation = (
        f"Regime classified as {regime}.",
        f"Selected strategy: {strategy}.",
        f"Relative volume is {snapshot.relative_volume:.2f}x.",
        f"Estimated spread is {snapshot.spread_bps:.1f} bps.",
        f"Expected holding period is {hold} day(s).",
    )
    return OpportunityScore(
        symbol=snapshot.symbol,
        asset_class=snapshot.asset_class,
        alpha_score=alpha_score,
        confidence=confidence,
        regime=regime,
        strategy=strategy,
        expected_holding_days=hold,
        components={key: round(value, 6) for key, value in components.items()},
        explanation=explanation,
    )
