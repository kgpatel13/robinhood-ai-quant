# Phase 8 — Robust Strategy Discovery

Phase 8.9 combines the complete 8.x research program without weakening Phase 7.10.

## Scope

- **8.0 Diagnostics:** gate-failure matrix, threshold gaps, primary rejection reason.
- **8.1 Experiment lineage:** SQLite experiment, candidate, status, and artifact registry.
- **8.2 Candidate generation:** deterministic default/grid/random hybrid candidates.
- **8.3 Walk-forward candidate evaluation:** fixed candidate parameters tested only out of sample.
- **8.4 Neighborhood stability:** nearby candidates must deliver comparable OOS behavior.
- **8.5 Cross-asset discovery:** every candidate is evaluated over the configured universe.
- **8.6 Feature snapshots:** lagged return, momentum, volatility, trend, and drawdown research data.
- **8.7 Explainable ranking:** readiness score and failed-gate explanation.
- **8.8 Automatic promotion loop:** completed candidates flow directly through Phase 7.10.
- **8.9 Reproducibility and resume:** manifests, hashes, database status, and cached candidate runs.

## Safety boundary

Phase 8 is research only. It does not place orders or connect to a broker. Phase 7.10 remains the mandatory promotion authority. Thresholds are not relaxed to force eligibility.

## Run a small validation

```powershell
python .\scripts\phase8_bundle.py `
  --symbols SPY QQQ BTC-USD `
  --strategies moving_average_cross rsi_mean_reversion `
  --max-candidates 3 `
  --monte-carlo-runs 200 `
  --output reports\phase8_smoke
```

## Run the full Phase 8 universe

```powershell
python .\scripts\phase8_bundle.py `
  --symbols SPY QQQ BTC-USD `
  --max-candidates 12 `
  --output reports\phase8_full
```

The full run can take substantial time because each parameter candidate is independently walk-forward tested across every asset.
