# Phase 11.2.1 — Label Intelligence Hardening

Phase 11.2.1 strengthens label approval before baseline-model training.

## Changes

- Samples complete `(timestamp, symbol)` events so all available holding periods remain together.
- Enforces minimum sample size, positive-label rate, extreme-return fraction, and label-quality thresholds per horizon.
- Prevents negative unconditional mean returns from receiving positive directional-signal credit.
- Classifies eligible horizons as `PRIMARY`, `SECONDARY`, or `EXPLORATORY`; failed horizons are `REVIEW`.
- Adds guardrail evidence to `horizon_quality.csv` and priority lists to the sign-off JSON.
- Runs Phase 11.2.1 in both Phase 11 smoke scripts.

## Default priority thresholds

- `PRIMARY`: label quality index >= 0.90
- `SECONDARY`: label quality index >= 0.85
- `EXPLORATORY`: label quality index >= 0.55
- `REVIEW`: any configured guardrail fails

These classifications authorize research only. Paper and live trading remain blocked.
