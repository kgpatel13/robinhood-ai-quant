from pathlib import Path

import pytest

from src.data.demo import make_demo_bars
from src.main import build_parser, run


def test_portfolio_backtest_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = Path(__file__).parents[2] / "config"
    for source in source_config.glob("*.yaml"):
        destination = tmp_path / "config" / source.name
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    first = tmp_path / "AAA.parquet"
    second = tmp_path / "BBB.parquet"
    make_demo_bars("AAA", rows=100).to_parquet(first, index=False)
    make_demo_bars("BBB", rows=100).to_parquet(second, index=False)
    args = build_parser().parse_args(
        [
            "portfolio-backtest-run",
            "--asset",
            f"AAA={first}",
            "--asset",
            f"BBB={second}",
            "--fast",
            "5",
            "--slow",
            "20",
            "--allocation",
            "equal",
            "--report-name",
            "integration",
        ]
    )
    assert run(args) == 0
    assert (tmp_path / "reports" / "portfolios" / "integration_report.html").exists()
