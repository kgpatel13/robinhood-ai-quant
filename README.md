# Robinhood AI Quant — Phases 1 through 4

A broker-independent quantitative research platform. It downloads and validates daily market data,
stores normalized Parquet datasets, runs reproducible single-asset and multi-asset backtests, and
produces performance reports. It cannot authenticate with a broker or place live orders.

## Phase 4.5 capabilities

- Extensible plugin registry for strategies, providers, allocators, reporters, brokers, risk models, and AI models.
- Dependency-injection service container.
- Typed event bus and execution run IDs.
- Runtime metrics collector and broker protocol foundation.
- `plugin-list` CLI command for architecture inspection.

- Multi-asset portfolio simulation on synchronized datasets
- Equal, fixed, and inverse-volatility allocation
- Daily, weekly, and monthly rebalancing
- Maximum asset-weight and cash-buffer controls
- Portfolio-level commissions and slippage
- Per-symbol holdings, target weights, orders, and realized P&L
- JSON metrics, CSV ledgers, PNG charts, and a self-contained HTML summary

Phase 3 single-asset capabilities remain available, including SMA, EMA, RSI, ATR, MACD,
Bollinger Bands, VWAP, the strategy registry, and next-bar-open execution.

See `docs/PHASE4_PORTFOLIO_RESEARCH.md` for design details.

## Upgrade on Windows

Keep the existing `.git`, `.venv`, `.env`, and generated data directories. Copy this package over
the existing project and approve file replacement.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Get-ChildItem .\scripts\*.ps1 | Unblock-File
python -m src.main config-validate
.\scripts\run_checks.ps1
.\scripts\phase4_smoke_test.ps1
```

Configuration validation should report **8 files**.

## Single-asset backtest

```powershell
python -m src.main backtest-run `
  --path data\validated\stock\SPY.parquet `
  --strategy moving_average_cross `
  --fast 50 `
  --slow 200
```

## Multi-asset portfolio backtest

```powershell
python -m src.main portfolio-backtest-run `
  --asset SPY=data\validated\stock\SPY.parquet `
  --asset QQQ=data\validated\stock\QQQ.parquet `
  --asset BTC-USD=data\validated\crypto\BTC-USD.parquet `
  --strategy moving_average_cross `
  --fast 20 `
  --slow 100 `
  --allocation inverse_volatility `
  --vol-lookback 30 `
  --rebalance weekly `
  --max-asset-weight 0.60 `
  --cash-buffer-pct 0.02
```

Reports are generated under `reports/portfolios/` and are ignored by Git.

## Safety boundary

The following remain disabled or absent:

- Robinhood credentials and brokerage authentication
- Live or broker-connected paper order submission
- Margin, leverage, short selling, and options
- Autonomous AI trading decisions
