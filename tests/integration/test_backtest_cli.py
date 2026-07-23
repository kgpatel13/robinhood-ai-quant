from pathlib import Path

from src.data.demo import make_demo_bars
from src.main import build_parser, run


def test_backtest_cli_writes_reports(tmp_path: Path, monkeypatch: object) -> None:
    data_path = tmp_path / "DEMO.parquet"
    make_demo_bars(rows=120).to_parquet(data_path, index=False)
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))  # type: ignore[attr-defined]
    args = build_parser().parse_args(
        ["backtest-run", "--path", str(data_path), "--fast", "5", "--slow", "20"]
    )
    assert run(args) == 0
    assert list((tmp_path / "reports" / "backtests").glob("*_metrics.json"))
