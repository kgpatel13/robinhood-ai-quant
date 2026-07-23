from pathlib import Path

import pytest

from src.data.demo import make_demo_bars
from src.main import build_parser, run


def test_optimization_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = Path(__file__).parents[2] / "config"
    for source in source_config.glob("*.yaml"):
        destination = tmp_path / "config" / source.name
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    data_path = tmp_path / "AAA.parquet"
    make_demo_bars("AAA", rows=100).to_parquet(data_path, index=False)
    args = build_parser().parse_args(
        [
            "optimize-run",
            "--path",
            str(data_path),
            "--param",
            "fast_period=5,10",
            "--param",
            "slow_period=20,30",
            "--report-name",
            "integration",
        ]
    )
    assert run(args) == 0
    assert (tmp_path / "reports" / "optimization" / "integration" / "leaderboard.csv").exists()
