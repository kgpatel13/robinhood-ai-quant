from __future__ import annotations

from src.alpha_intelligence.models import ParameterSpec, StrategyDefinition, StrategyFamily


def default_strategy_templates() -> tuple[StrategyDefinition, ...]:
    return (
        StrategyDefinition(
            strategy_id="trend-moving-average",
            name="Moving Average Trend",
            family=StrategyFamily.TREND,
            version="1.0.0",
            parameters=(
                ParameterSpec("fast_window", (10, 20, 30)),
                ParameterSpec("slow_window", (50, 100, 200)),
            ),
            tags=("trend", "daily"),
        ),
        StrategyDefinition(
            strategy_id="rsi-mean-reversion",
            name="RSI Mean Reversion",
            family=StrategyFamily.MEAN_REVERSION,
            version="1.0.0",
            parameters=(
                ParameterSpec("rsi_window", (7, 14, 21)),
                ParameterSpec("entry_level", (20, 25, 30)),
                ParameterSpec("exit_level", (50, 55, 60)),
            ),
            tags=("mean-reversion", "daily"),
        ),
        StrategyDefinition(
            strategy_id="range-breakout",
            name="Range Breakout",
            family=StrategyFamily.BREAKOUT,
            version="1.0.0",
            parameters=(
                ParameterSpec("lookback", (20, 50, 100)),
                ParameterSpec("volatility_filter", (0.0, 0.5, 1.0)),
            ),
            tags=("breakout", "volatility"),
        ),
        StrategyDefinition(
            strategy_id="relative-strength-rotation",
            name="Relative Strength Rotation",
            family=StrategyFamily.RELATIVE_STRENGTH,
            version="1.0.0",
            parameters=(
                ParameterSpec("ranking_window", (20, 60, 120)),
                ParameterSpec("top_n", (3, 5, 10)),
            ),
            tags=("cross-sectional", "rotation"),
        ),
    )
