# ATLAS v16.3 — Unified Broker Manager

This overlay includes the v16.2 Robinhood Crypto API corrections plus the next safe execution phase.

## Added
- `UnifiedBrokerManager` with explicit equity/crypto routing.
- Consolidated broker connection and health reporting.
- Official Robinhood Crypto read-only broker adapter.
- Conversion of holdings and bid/ask quotes into Atlas account/position models.
- Fail-closed mutation methods: no live crypto order can be submitted, replaced, or cancelled.
- Unit coverage for routing, health, account conversion, and safety blocking.

## Fixed
- Python 3.12 `type` aliases required by Ruff UP040.
- Removed the obsolete mypy `type: ignore` comment.
- Repeated Robinhood symbol query parameters and pagination from v16.2 are included.

## Validation
Run Ruff, mypy, the focused tests, then the existing authenticated read-only diagnostic.
