from src.research.models import OptimizationConfig, ParameterSpec
from src.research.search import generate_candidates


def test_grid_candidates_are_deterministic() -> None:
    config = OptimizationConfig(
        strategy="moving_average_cross",
        parameters=(ParameterSpec("fast_period", (5, 10)), ParameterSpec("slow_period", (20, 30))),
    )
    assert generate_candidates(config) == [
        {"fast_period": 5, "slow_period": 20},
        {"fast_period": 5, "slow_period": 30},
        {"fast_period": 10, "slow_period": 20},
        {"fast_period": 10, "slow_period": 30},
    ]


def test_random_candidates_are_reproducible() -> None:
    config = OptimizationConfig(
        strategy="moving_average_cross",
        parameters=(
            ParameterSpec("fast_period", (5, 10, 15)),
            ParameterSpec("slow_period", (20, 30)),
        ),
        method="random",
        max_evaluations=3,
        seed=7,
    )
    assert generate_candidates(config) == generate_candidates(config)
    assert len(generate_candidates(config)) == 3
