# Phase 3 — Strategy Research and Backtesting

Phase 3 adds a broker-independent, long-only research backtester. Signals are calculated
using completed daily bars and shifted one bar before execution at the next bar's open,
which prevents same-bar look-ahead bias.

## Included

- Indicator library: SMA, EMA, RSI, ATR, MACD, Bollinger Bands, and VWAP
- Strategy interface and registry
- EMA crossover sample strategy
- Cash/position/equity accounting
- Commission and basis-point slippage assumptions
- Trade ledger and equity curve
- CAGR, volatility, Sharpe, Sortino, max drawdown, win rate, and profit factor
- JSON and CSV reports

## Run

```powershell
python -m src.main strategy-list
python -m src.main backtest-run --path data\validated\stock\SPY.parquet --strategy moving_average_cross --fast 50 --slow 200
```

This remains a research platform. It has no brokerage authentication or live-order capability.
