# Atlas Phase 10.1–10.3 — Broker Abstraction Foundation

Version 4.0.3 adds an adapter-ready brokerage boundary without enabling live trading.

## Included

- `BrokerAdapter` protocol
- Capability flags for adapter feature discovery
- Paper broker adapter over the existing deterministic execution engine
- Idempotent broker order router
- Retry policy driven by normalized error classification
- Append-only JSONL broker audit trail
- Explicit paper/live trading modes
- Hard default live-routing safety block

## Safety

The release remains paper-only. Live order routing is disabled by default and no live broker credentials are required or consumed.
