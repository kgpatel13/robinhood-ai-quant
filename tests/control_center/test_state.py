from datetime import UTC, datetime
from pathlib import Path

from src.control_center import IntradaySessionState, IntradayStateStore, PaperPosition


def test_state_round_trip(tmp_path: Path) -> None:
    store = IntradayStateStore(tmp_path / "state.json")
    state = IntradaySessionState("2026-07-27", 100_000.0, trades_today=2)
    state.positions["SPY"] = PaperPosition(
        "SPY", 5, 500, 501, "intraday_momentum", opened_at=datetime.now(UTC)
    )
    state.processed_decision_ids.add("abc")
    store.save(state)
    loaded = store.load()
    assert loaded.session_date == state.session_date
    assert loaded.trades_today == 2
    assert loaded.positions["SPY"].quantity == 5
    assert loaded.processed_decision_ids == {"abc"}


def test_new_session_does_not_reuse_old_state(tmp_path: Path) -> None:
    store = IntradayStateStore(tmp_path / "state.json")
    store.save(IntradaySessionState("2026-07-26", 90_000.0, trades_today=9))
    loaded = store.load_or_create("2026-07-27", 100_000.0)
    assert loaded.trades_today == 0
    assert loaded.starting_equity == 100_000.0
