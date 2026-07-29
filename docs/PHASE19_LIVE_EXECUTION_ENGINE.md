# Phase 19 — Reliable Execution Engine

Atlas v4.9.3 adds a broker-independent execution gateway with idempotency,
pre-trade reconciliation and safety gates, order notional/open-order limits,
size throttling, cancel/replace routing, and restart recovery.

Live trading remains disabled by default. Enabling it requires an explicit
`ExecutionPolicy(live_enabled=True)` plus broker safety configuration.
