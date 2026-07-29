# Atlas v10.0 — Integrated Controlled Paper Release

Atlas v10.0 connects the existing multi-agent, production-control, broker, execution,
and self-improving subsystems through one auditable orchestration cycle.

## Integrated cycle

1. Validate market-data freshness and operational mode.
2. Evaluate production health, reconciliation, deployment stage, and kill switch.
3. Build the agent context and obtain a supervised decision.
4. Translate the decision into a bounded order request.
5. Simulate in backtest/shadow mode or submit through the configured broker adapter.
6. Persist an append-only audit record and an atomic recovery checkpoint.
7. Produce approval-gated learning proposals from closed-trade feedback.

## Safety properties

- HALTED mode always blocks.
- Stale observations block before agent evaluation or execution.
- Risk/execution agent vetoes block the cycle.
- Live and canary modes require production safety approval.
- Canary sizing respects the production capital fraction.
- Short orders are disabled by default.
- Client order IDs use the cycle ID to preserve broker-level idempotency.
- Learning proposals do not alter active weights without explicit approval.
- No broker credentials or resolved secrets are stored in cycle records.

## Operational modes

- BACKTEST
- PAPER
- SHADOW
- CANARY
- LIVE
- HALTED

Backtest and shadow modes create the validated order intent but do not submit it.
Paper mode submits only to the configured paper broker. Canary and live modes remain
subject to the existing production controller, reconciliation gate, service-health gate,
and kill switch.

## New modules

- `trading_orchestrator.integration_models`
- `trading_orchestrator.translator`
- `trading_orchestrator.persistence`
- `trading_orchestrator.feedback`
- `trading_orchestrator.unified`

The legacy `PaperTradeOrchestrator` remains available for backward compatibility.
