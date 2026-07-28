from datetime import UTC, datetime, time, timedelta

from src.operations import CheckpointManager, HealthMonitor, HealthStatus, PaperKillSwitch
from src.runtime import EventBus, EventPriority, EventStore, EventType, RuntimeEvent
from src.session import StrategyOperatingProfile, TradingStyle, USMarketCalendar


def test_event_bus_orders_by_priority_and_persists(tmp_path) -> None:
    bus = EventBus()
    seen: list[str] = []
    store = EventStore(tmp_path / "events.jsonl")
    bus.subscribe_all(lambda event: (seen.append(event.payload["name"]), store.append(event)))
    bus.publish(RuntimeEvent(EventType.SIGNAL, {"name": "normal"}))
    bus.publish(RuntimeEvent(EventType.SYSTEM_ALERT, {"name": "critical"}, EventPriority.CRITICAL))

    assert bus.drain() == 2
    assert seen == ["critical", "normal"]
    assert [event.payload["name"] for event in store.read()] == seen


def test_market_session_and_forced_day_exit() -> None:
    calendar = USMarketCalendar()
    profile = StrategyOperatingProfile(
        TradingStyle.DAY_TRADING,
        allow_overnight=False,
        allow_weekend=False,
        forced_exit_time=time(15, 50),
    )
    regular = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)  # 11:00 ET
    exit_time = datetime(2026, 7, 27, 19, 51, tzinfo=UTC)  # 15:51 ET

    assert calendar.entry_allowed(profile, regular)
    assert calendar.force_exit_due(profile, exit_time)


def test_health_monitor_detects_stale_heartbeat() -> None:
    monitor = HealthMonitor(heartbeat_timeout=timedelta(seconds=10))
    start = datetime(2026, 1, 1, tzinfo=UTC)
    monitor.heartbeat("market_data", at=start)
    assert monitor.overall_status(now=start + timedelta(seconds=11)) is HealthStatus.UNHEALTHY


def test_checkpoint_and_kill_switch(tmp_path) -> None:
    manager = CheckpointManager(tmp_path)
    manager.save("runtime", {"cycle": 7, "positions": ["AAPL"]})
    assert manager.load("runtime") == {"cycle": 7, "positions": ["AAPL"]}

    switch = PaperKillSwitch()
    switch.engage("stale feed")
    assert switch.engaged
    try:
        switch.ensure_trading_allowed()
    except RuntimeError as exc:
        assert "stale feed" in str(exc)
    else:
        raise AssertionError("kill switch should block trading")
