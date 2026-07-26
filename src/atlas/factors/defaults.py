from __future__ import annotations

from src.atlas.factors.core import (
    FactorComponent,
    FactorDefinition,
    FactorMetadata,
    FactorRegistry,
    NormalizationMethod,
)


def build_default_registry() -> FactorRegistry:
    registry = FactorRegistry()
    definitions = (
        FactorMetadata(
            name="momentum",
            category="return",
            description="Multi-horizon price momentum with short-term reversal de-emphasis.",
            components=(
                FactorComponent("return_20d", 1.0),
                FactorComponent("return_60d", 1.5),
                FactorComponent("return_120d", 1.5),
                FactorComponent("return_252d", 1.0),
                FactorComponent("return_5d", 0.5, -1),
            ),
            minimum_components=2,
        ),
        FactorMetadata(
            name="trend",
            category="technical",
            description="Price location and persistence relative to medium- and long-term trends.",
            components=(
                FactorComponent("price_to_sma_20", 1.0),
                FactorComponent("price_to_sma_50", 1.25),
                FactorComponent("price_to_sma_100", 1.0),
                FactorComponent("price_to_sma_200", 1.0),
                FactorComponent("trend_persistence_20", 0.75),
                FactorComponent("trend_persistence_60", 1.0),
            ),
            minimum_components=2,
        ),
        FactorMetadata(
            name="low_volatility",
            category="risk",
            description="Preference for assets with lower realized and range-based volatility.",
            components=(
                FactorComponent("volatility_20d", 1.0, -1),
                FactorComponent("volatility_60d", 1.5, -1),
                FactorComponent("volatility_120d", 1.0, -1),
                FactorComponent("atr_pct_20", 1.0, -1),
                FactorComponent("bollinger_width_20", 0.5, -1),
            ),
            minimum_components=2,
        ),
        FactorMetadata(
            name="liquidity",
            category="capacity",
            description="Dollar-volume capacity and recent trading activity.",
            components=(
                FactorComponent("average_dollar_volume_20d", 1.5),
                FactorComponent("average_dollar_volume_60d", 1.5),
                FactorComponent("relative_volume_20d", 0.5),
                FactorComponent("money_flow_ratio_20", 0.5),
            ),
            minimum_components=2,
        ),
        FactorMetadata(
            name="mean_reversion",
            category="technical",
            description="Preference for oversold assets positioned below recent ranges and bands.",
            components=(
                FactorComponent("rsi_14", 1.0, -1),
                FactorComponent("stochastic_20", 1.0, -1),
                FactorComponent("bollinger_z_20", 1.0, -1),
                FactorComponent("return_5d", 0.75, -1),
                FactorComponent("distance_from_high_20", 0.5, -1),
            ),
            minimum_components=2,
        ),
        FactorMetadata(
            name="data_quality",
            category="quality",
            description="History depth and continuity of the underlying market data.",
            components=(
                FactorComponent("bar_count", 1.0),
                FactorComponent("zero_volume_ratio_60", 1.0, -1),
                FactorComponent("gap_ratio_60", 0.75, -1),
            ),
            normalization=NormalizationMethod.PERCENTILE,
            minimum_components=2,
        ),
    )
    for metadata in definitions:
        registry.register(FactorDefinition(metadata=metadata))
    return registry
