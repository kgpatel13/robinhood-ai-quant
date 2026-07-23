# Phase 4.5 — Platform Architecture

Version: 0.4.5

Phase 4.5 introduces a stable extensibility layer without changing existing CLI behavior.

## Components

- Plugin registry for strategies, providers, allocators, reporters, brokers, risk models, and AI models.
- Service container supporting singleton instances and lazy factories.
- Typed synchronous event bus.
- Execution context with run IDs and timestamps.
- Lightweight metrics collector and timers.
- Broker protocol foundation for future paper and live execution.
- Application bootstrap that registers all built-in capabilities.

## Compatibility

All Phase 1–4 commands and configuration files remain supported. The existing strategy helper API now delegates to the shared plugin registry.

## Plugin development

Create a `PluginDescriptor`, select a `PluginType`, and register it in a `PluginRegistry`. Duplicate registrations are rejected unless `replace=True` is explicitly provided.

## Safety

This phase does not enable live trading, margin, leverage, short selling, or options.
