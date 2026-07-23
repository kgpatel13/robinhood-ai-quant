# Foundation Risk Policy

## Prohibited

- Leverage
- Margin
- Short selling
- Options
- Martingale
- Grid averaging
- Unbounded averaging down
- Unapproved assets
- Unlogged decisions
- Direct AI deployment to production

## Fail closed

When the system cannot prove that data, broker state, portfolio state, or risk
controls are valid, it must reject new trades.

## Control flow

Strategy proposes -> portfolio evaluates -> risk approves/rejects -> execution submits.
