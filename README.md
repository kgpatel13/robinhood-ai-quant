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

## Phase 5A: Research and Optimization

Version 0.5.0 adds grid search, seeded random search, objective-based strategy ranking,
optional multiprocessing, reproducible research metadata, and optimization reports.
See `docs/PHASE5A_OPTIMIZATION.md` for usage.

## Phase 9: Cross-Market Opportunity Scanner

Version 0.9.0 adds separate stock and crypto research profiles, broad symbol scanning,
soft opportunity scoring, hard liquidity/risk controls, ATR-based position plans, and
symbol-level failure isolation. See `docs/PHASE9_OPPORTUNITY_SCANNER.md`.

```powershell
python .\scripts\phase9_bundle.py --symbols SPY QQQ BTC-USD --top-n 10 --output reports\phase9_smoke
```

Omit `--symbols` to scan every validated dataset. Phase 9 is research-only and does not place orders.
