from __future__ import annotations

import json

from src.main import build_parser, run


def test_plugin_list_cli(capsys: object) -> None:
    args = build_parser().parse_args(["plugin-list"])
    assert run(args) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    names = {item["name"] for item in payload}
    assert {"moving_average_cross", "yahoo", "equal", "portfolio"} <= names
