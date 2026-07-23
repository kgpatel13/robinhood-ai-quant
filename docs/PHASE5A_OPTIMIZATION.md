# Phase 5A — Research and Optimization Engine

Phase 5A adds deterministic grid search, seeded random search, objective-based ranking,
optional multiprocessing, reproducible metadata, and optimization reports.

## CLI example

```powershell
python -m src.main optimize-run `
  --path data/validated/stock/SPY.parquet `
  --strategy moving_average_cross `
  --param fast_period=5,10,15,20 `
  --param slow_period=50,100,150,200 `
  --method grid `
  --objective sharpe `
  --workers 1 `
  --report-name spy_ma_grid
```

Use `--method random --max-evaluations 20 --seed 42` to sample a large parameter space
reproducibly. Increase `--workers` only after the serial run succeeds in the local environment.

Generated artifacts include CSV and JSON leaderboards, metadata, the best equity curve,
a chart, and an HTML summary.

Phase 5A performs in-sample research. Phase 5B will add walk-forward, out-of-sample, parameter
stability, and Monte Carlo robustness analysis.
