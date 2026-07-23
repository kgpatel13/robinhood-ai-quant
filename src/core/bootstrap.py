from __future__ import annotations

from dataclasses import dataclass

from src.common.config import AppSettings
from src.core.events import EventBus
from src.core.metrics import MetricsCollector
from src.core.plugins import PluginDescriptor, PluginRegistry, PluginType
from src.core.services import ServiceContainer
from src.data.providers.coingecko import CoinGeckoProvider
from src.data.providers.yahoo import YahooFinanceProvider
from src.portfolio.allocation import equal_weights, fixed_weights, inverse_volatility_weights
from src.reporting import write_backtest_report, write_portfolio_report
from src.strategies.moving_average import MovingAverageCrossStrategy


@dataclass(frozen=True)
class ApplicationRuntime:
    settings: AppSettings
    plugins: PluginRegistry
    services: ServiceContainer
    events: EventBus
    metrics: MetricsCollector


def build_plugin_registry() -> PluginRegistry:
    registry = PluginRegistry()
    entries = (
        PluginDescriptor("moving_average_cross", PluginType.STRATEGY, MovingAverageCrossStrategy),
        PluginDescriptor("yahoo", PluginType.DATA_PROVIDER, YahooFinanceProvider),
        PluginDescriptor("coingecko", PluginType.DATA_PROVIDER, CoinGeckoProvider),
        PluginDescriptor("equal", PluginType.ALLOCATOR, equal_weights),
        PluginDescriptor("fixed", PluginType.ALLOCATOR, fixed_weights),
        PluginDescriptor("inverse_volatility", PluginType.ALLOCATOR, inverse_volatility_weights),
        PluginDescriptor("backtest", PluginType.REPORTER, write_backtest_report),
        PluginDescriptor("portfolio", PluginType.REPORTER, write_portfolio_report),
    )
    for descriptor in entries:
        registry.register(descriptor)
    return registry


def build_runtime(settings: AppSettings) -> ApplicationRuntime:
    plugins = build_plugin_registry()
    services = ServiceContainer()
    events = EventBus()
    metrics = MetricsCollector()
    services.register_instance("settings", settings)
    services.register_instance("plugins", plugins)
    services.register_instance("events", events)
    services.register_instance("metrics", metrics)
    return ApplicationRuntime(settings, plugins, services, events, metrics)
