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
