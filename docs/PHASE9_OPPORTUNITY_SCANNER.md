# Phase 9 — Cross-Market Opportunity Scanner

Phase 9 introduces a broad, restart-safe research scanner that evaluates every validated symbol and produces separate stock and crypto rankings.

## Design decisions

- Stocks and crypto use independent thresholds, feature weights, position sizing, stops, and targets.
- Liquidity, price validity, minimum history, and account-risk constraints are hard filters.
- Trend, momentum, volume, volatility, market structure, and optional news risk are combined into a soft 0–100 opportunity score.
- The default entry thresholds (62 stocks, 64 crypto) are intentionally less restrictive than Phase 7 promotion gates. This creates paper-trading candidates without weakening account protection.
- Phase 9 emits research candidates only. It does not submit live broker orders.

## Run

```powershell
python .\scripts\phase9_bundle.py `
  --symbols SPY QQQ BTC-USD `
  --top-n 10 `
  --output reports\phase9_smoke
```

To scan every symbol already stored under `data/validated`, omit `--symbols`.

## Outputs

- `opportunity_ranking.csv`: every successfully scanned symbol, including rejection reasons.
- `stock_opportunities.csv`: top eligible stock candidates.
- `crypto_opportunities.csv`: top eligible crypto candidates.
- `scan_failures.json`: symbol-level failures; one bad dataset does not stop the full run.
- `manifest.json`: configuration and run summary.

## Interpretation

An eligible row means the symbol passed Phase 9's research-entry threshold and hard safety filters. It is not proof of future profitability. Phase 10 should replay these ranked signals through realistic intraday or daily execution, including spreads, slippage, latency, and portfolio limits.
