from pathlib import Path

from src.main import build_parser, run


def test_offline_demo_and_status(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    # The configured validated path is project-relative by design; run in temporary cwd.
    monkeypatch.chdir(tmp_path)
    source_config = Path(__file__).parents[2] / "config"
    monkeypatch.setenv("CONFIG_DIR", str(source_config))
    assert run(build_parser().parse_args(["data-demo", "--symbol", "DEMO"])) == 0
    assert Path("data/validated/stock/DEMO.parquet").exists()
    assert run(build_parser().parse_args(["data-status"])) == 0
    assert "DEMO" in capsys.readouterr().out
