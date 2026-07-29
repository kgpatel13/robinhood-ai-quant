# Atlas v4.5.3 — Phase 15.1–15.3 Production Readiness

## Phase 15.1 — Unified Paper Trade Orchestration

`src/trading_orchestrator` converts alpha, regime, market-quality, and strategy-health
inputs into one deterministic paper-trade intent. It can approve, reduce, or reject a
trade and records the exact reasons and final notional multiplier.

## Phase 15.2 — Strategy Promotion Governance

`src/promotion_governance` enforces auditable evidence requirements before a strategy
can move from research to shadow and from shadow to paper. Paper strategies are never
automatically promoted to live execution; manual approval remains mandatory.

## Phase 15.3 — Independent Production Safety Guard

`src/production_safety` provides an independent halt/throttle layer covering stale data,
broker disconnection, daily loss, drawdown, rejection-rate, loss-streak, and manual
kill-switch conditions. The module is broker-independent and safe for paper deployment.

## Packaging correction

The package manifest now includes all Phase 13–15 packages so editable and wheel installs
ship the complete platform rather than relying on the source tree being present.
