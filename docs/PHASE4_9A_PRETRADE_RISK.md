# Phase 4.9A — Pre-Trade Institutional Risk Engine

Every order proposed by daily orchestration now passes through deterministic pre-trade risk evaluation before broker routing.

## Controls

- Maximum position weight
- Maximum order notional
- Maximum gross exposure
- Minimum cash reserve
- Maximum open positions
- Minimum order notional
- Long-position availability for sells
- Valid price and quantity checks

## Decisions

Each order receives one outcome:

- `approve`
- `resize`
- `reject`

Every decision includes a machine-readable reason code and is written to the execution journal as a `risk_decision` event.

## Sequential evaluation

Orders are evaluated in plan order. Sells release simulated cash and exposure before later buys are evaluated. Approved buys consume simulated cash and exposure so subsequent orders cannot exceed portfolio limits.
