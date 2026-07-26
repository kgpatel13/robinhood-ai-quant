from __future__ import annotations

from src.atlas.features.core import FeatureContext, FeatureRegistry, register_feature


def register(registry: FeatureRegistry) -> None:
    register_feature(
        registry,
        name="bar_count",
        category="quality",
        description="Number of available OHLCV bars.",
        unit="count",
        compute=lambda context: float(len(context.bars)),
    )
    register_feature(
        registry,
        name="zero_volume_ratio_60",
        category="quality",
        description="Fraction of zero-volume bars in the most recent 60 bars.",
        window=60,
        minimum=0.0,
        maximum=1.0,
        compute=lambda context: _zero_volume_ratio(context, 60),
    )
    register_feature(
        registry,
        name="gap_ratio_60",
        category="quality",
        description="Mean absolute overnight price gap over the most recent 60 bars.",
        window=60,
        compute=lambda context: _gap_ratio(context, 60),
    )


def _zero_volume_ratio(context: FeatureContext, period: int) -> float | None:
    selected = context.bars[-period:]
    return None if not selected else sum(bar.volume == 0.0 for bar in selected) / len(selected)


def _gap_ratio(context: FeatureContext, period: int) -> float | None:
    if len(context.bars) < 2:
        return None
    selected = context.bars[-(period + 1):]
    gaps: list[float] = []
    for previous, current in zip(selected[:-1], selected[1:], strict=True):
        if previous.close > 0.0:
            gaps.append(abs(current.open / previous.close - 1.0))
    return None if not gaps else sum(gaps) / len(gaps)
