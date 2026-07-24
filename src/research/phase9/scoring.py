from __future__ import annotations

from dataclasses import dataclass

from src.research.phase9.models import AssetClass


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    trend: float
    momentum: float
    volume: float
    volatility: float
    structure: float
    news: float


def _clip(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return min(upper, max(lower, value))


def score_opportunity(
    features: dict[str, float], asset_class: AssetClass, news_risk: float = 0.0
) -> ScoreBreakdown:
    trend = _clip(50 + features["trend_fast_slow"] * 900 + features["trend_50_200"] * 350)
    momentum = _clip(50 + features["momentum_5"] * 500 + features["momentum_21"] * 250)
    volume = _clip(30 + min(features["relative_volume"], 3.0) * 25)
    ideal_volatility = 0.65 if asset_class == "crypto" else 0.35
    volatility_distance = abs(features["annualized_volatility"] - ideal_volatility)
    volatility = _clip(100 - volatility_distance * 100)
    rsi_bonus = 100 - min(abs(features["rsi_14"] - 58.0) * 2.2, 100)
    breakout_bonus = _clip(50 + features["breakout_20"] * 700)
    structure = _clip(0.55 * rsi_bonus + 0.45 * breakout_bonus)
    news = _clip(100 * (1.0 - news_risk))

    weights = (
        (0.25, 0.22, 0.16, 0.12, 0.18, 0.07)
        if asset_class == "stock"
        else (0.22, 0.26, 0.18, 0.14, 0.15, 0.05)
    )
    total = sum(
        weight * value
        for weight, value in zip(
            weights, (trend, momentum, volume, volatility, structure, news), strict=True
        )
    )
    return ScoreBreakdown(
        total=round(_clip(total), 4),
        trend=round(trend, 4),
        momentum=round(momentum, 4),
        volume=round(volume, 4),
        volatility=round(volatility, 4),
        structure=round(structure, 4),
        news=round(news, 4),
    )
