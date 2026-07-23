from pathlib import Path

from src.data.demo import make_demo_bars
from src.research import (
    OptimizationConfig,
    OptimizationEngine,
    ParameterSpec,
    write_optimization_report,
)


def test_optimization_report_writes_artifacts(tmp_path: Path) -> None:
    result = OptimizationEngine().run(
        make_demo_bars("TEST", rows=100),
        OptimizationConfig(
            strategy="moving_average_cross",
            parameters=(
                ParameterSpec("fast_period", (5,)),
                ParameterSpec("slow_period", (20,)),
            ),
        ),
    )
    paths = write_optimization_report(result, tmp_path, "run")
    assert set(paths) == {
        "leaderboard_csv",
        "leaderboard_json",
        "metadata",
        "best_equity_csv",
        "best_equity_chart",
        "summary_html",
    }
    assert all(path.exists() for path in paths.values())
