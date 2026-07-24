# Phase 6 — Strategy Factory (v0.6.8)

This bundle completes Phase 6.0 through 6.8:

- 6.0 strategy plugin contract and registry
- 6.1 Moving Average Cross migration
- 6.2 RSI Mean Reversion
- 6.3 Donchian Breakout
- 6.4 Turtle Trading
- 6.5 Bollinger Mean Reversion
- 6.6 ATR Breakout
- 6.7 cross-strategy, cross-asset tournament
- 6.8 equal-weight voting ensemble portfolio

Run a small tournament:

```powershell
python .\scripts\phase6_bundle.py --symbols SPY QQQ BTC-USD
```

The tournament reuses the complete Phase 5 walk-forward, transaction-cost, benchmark,
stability, and scorecard pipeline. The ensemble is a research baseline, not a live allocation model.
