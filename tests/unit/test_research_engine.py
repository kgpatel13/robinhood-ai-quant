import pytest

from src.data.demo import make_demo_bars
from src.research import OptimizationConfig, OptimizationEngine, ParameterSpec


def test_optimization_engine_ranks_trials() -> None:
    result = OptimizationEngine().run(
        make_demo_bars("TEST", rows=120),
        OptimizationConfig(
            strategy="moving_average_cross",
            parameters=(
                ParameterSpec("fast_period", (5, 10)),
                ParameterSpec("slow_period", (20, 30)),
            ),
            objective="sharpe",
        ),
    )
    assert len(result.trials) == 4
    assert [trial.rank for trial in result.trials] == [1, 2, 3, 4]
    assert result.trials[0].score >= result.trials[-1].score


def test_optimizer_skips_invalid_parameter_combinations() -> None:
    config = OptimizationConfig(
        strategy="moving_average_cross",
        parameters=(
            ParameterSpec("fast_period", (5, 50)),
            ParameterSpec("slow_period", (20, 50)),
        ),
        workers=1,
    )

    result = OptimizationEngine().run(make_demo_bars("TEST", rows=120), config)

    assert result.trials
    assert all(
        trial.parameters["fast_period"] < trial.parameters["slow_period"] for trial in result.trials
    )
    assert len(result.trials) == 2


def test_optimizer_rejects_parameter_space_with_no_valid_candidates() -> None:
    config = OptimizationConfig(
        strategy="moving_average_cross",
        parameters=(
            ParameterSpec("fast_period", (50,)),
            ParameterSpec("slow_period", (20, 50)),
        ),
        workers=1,
    )

    with pytest.raises(ValueError, match="no valid candidates"):
        OptimizationEngine().run(make_demo_bars("TEST", rows=120), config)
