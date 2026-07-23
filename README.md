# Robinhood AI Quant — Phases 1, 2, and 3

A broker-independent quantitative research platform. It downloads and validates daily market
data, stores normalized Parquet datasets, runs reproducible strategy backtests, and produces
performance reports. It cannot authenticate with a broker or place live orders.

## Phase 3 capabilities

- SMA, EMA, RSI, ATR, MACD, Bollinger Bands, and VWAP
- Extensible strategy interface and registry
- Long-only EMA crossover reference strategy
- Signals calculated at bar close and executed at the next bar open
- Configurable commissions and slippage
- Cash, position, trade, and equity accounting
- CAGR, annualized volatility, Sharpe, Sortino, maximum drawdown, win rate, and profit factor
- JSON metrics, CSV ledgers, equity chart, and drawdown chart

See `docs/PHASE3_BACKTESTING.md` for design details.

## Replace or upgrade on Windows

Keep the existing `.git` and `.venv` directories. Copy this package's project contents over the
existing project and approve file replacement. The distribution ZIP intentionally excludes local
secrets, generated data, caches, `.git`, and `.venv`.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Get-ChildItem .\scripts\*.ps1 | Unblock-File
python -m src.main config-validate
.\scripts\run_checks.ps1
.\scripts\phase3_smoke_test.ps1
```

Configuration validation should report **7 files**.

## Market data

```powershell
python -m src.main data-download `
  --symbol SPY `
  --asset-class stock `
  --start 2020-01-01 `
  --end 2026-07-22 `
  --provider yahoo
```

Yahoo remains the primary Phase 2 provider. CoinGecko is optional and can be ignored.

## Backtest SPY

```powershell
python -m src.main strategy-list
python -m src.main backtest-run `
  --path data\validated\stock\SPY.parquet `
  --strategy moving_average_cross `
  --fast 50 `
  --slow 200 `
  --initial-cash 100000 `
  --commission 0 `
  --slippage-bps 2
```

Reports are generated under `reports/backtests/` and are ignored by Git.

## Safety boundary

The following remain disabled or absent:

- Robinhood credentials
- Brokerage authentication
- Live and paper order submission
- Margin, leverage, short selling, and options
- Autonomous AI trading decisions
