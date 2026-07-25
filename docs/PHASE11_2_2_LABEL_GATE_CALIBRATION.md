# Phase 11.2.2 — Label Gate Calibration

Phase 11.2.2 corrects cross-horizon approval behavior.

- `extreme_return_fraction` and `extreme_return_passed` remain in reports.
- Extreme-return frequency is informational because raw-return tails naturally grow with holding period.
- Horizon approval now depends on minimum rows, class balance, label quality, and leakage diagnostics.
- A regression test ensures legitimate large returns cannot independently reject a horizon.
- Paper and live trading remain blocked.
