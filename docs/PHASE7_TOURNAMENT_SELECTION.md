# Phase 7 — Tournament Selection and Promotion

Phase 7 converts Phase 6 tournament output into a deterministic strategy lifecycle and paper-trading eligibility decision.

## Capabilities

- 7.0: versioned selection models and orchestration
- 7.1: benchmark-relative metrics
- 7.2: weighted composite scoring
- 7.3: hard promotion gates
- 7.4: cross-asset consistency
- 7.5: parameter-stability integration
- 7.6: regime and Monte Carlo primitives
- 7.7: lifecycle states and ranking
- 7.8: promotion/rejection reports
- 7.9: deterministic manifests and quality gates

## Run

```powershell
python .\scripts\phase7_bundle.py `
  --tournament reports\phase6_9_smoke\tournament\strategy_tournament.csv `
  --output reports\phase7_smoke
```

## Outputs

- `phase7_leaderboard.csv`
- `paper_trading_eligible.csv`
- `rejections.csv`
- `promotion_report.json`
- `manifest.json`

A high rank does not imply promotion. Every hard gate must pass for paper-trading eligibility.
