# ATLAS v17.1 — Persistent Ledger and Shadow Execution

This phase adds a restart-safe SQLite trading ledger and a fail-closed shadow execution engine.

## Included

- Durable orders, fills, account snapshots, and risk events
- Portfolio reconstruction from fills after restart
- Cash, market value, equity, realized P&L, and unrealized P&L
- Configurable slippage, commission, and maximum order notional
- Insufficient-cash and insufficient-position checks
- Optional external risk gate
- CLI demo and regression tests

No Robinhood mutation endpoint is called. Shadow fills are local simulations only.
