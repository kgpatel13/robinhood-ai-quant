from __future__ import annotations

from pathlib import Path

from src.common.config import AppSettings
from src.core.bootstrap import build_runtime
from src.core.context import ExecutionContext
from src.core.metrics import MetricsCollector, Timer
from src.core.plugins import PluginType


def settings() -> AppSettings:
    return AppSettings(
        "test",
        "INFO",
        Path("config"),
        Path("data"),
        Path("reports"),
        Path("logs"),
        30,
        3,
    )


def test_runtime_registers_builtins_and_services() -> None:
    runtime = build_runtime(settings())
    assert "moving_average_cross" in runtime.plugins.names(PluginType.STRATEGY)
    assert "yahoo" in runtime.plugins.names(PluginType.DATA_PROVIDER)
    assert runtime.services.resolve("plugins") is runtime.plugins


def test_execution_context_has_unique_run_ids() -> None:
    first = ExecutionContext.create("one", "test")
    second = ExecutionContext.create("two", "test")
    assert first.run_id != second.run_id
    assert first.command == "one"


def test_metrics_counter_and_timing_snapshot() -> None:
    metrics = MetricsCollector()
    metrics.increment("runs")
    with Timer(metrics, "work"):
        pass
    snapshot = metrics.snapshot()
    assert snapshot["counters"] == {"runs": 1.0}
    timings = snapshot["timings"]
    assert isinstance(timings, dict)
    assert timings["work"]["count"] == 1
