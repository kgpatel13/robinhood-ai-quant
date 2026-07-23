# Robinhood AI Quant — Phases 1 and 2

A broker-independent quantitative research foundation. Phase 2 adds historical market-data
providers, normalization, Parquet storage, manifests, quality validation, and an offline demo.
It still cannot place orders and requires no Robinhood credentials.

## Phase 2.0.1 compatibility fixes

- Adds SciPy because yfinance price repair uses it.
- Corrects the Windows smoke-test path.
- Produces a clear error when CoinGecko is used without an API key.

## Upgrade an existing Phase 1 folder on Windows

1. Commit or back up the existing Phase 1 folder.
2. Extract this ZIP to a temporary folder.
3. Copy the extracted project contents into `C:\Projects
obinhood-ai-quant` and approve
   replacement. Do **not** copy a `.git` or `.venv` folder; this package contains neither.
4. Open PowerShell in the project root and run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m src.main config-validate
.\scripts
un_checks.ps1
.\scripts\phase2_smoke_test.ps1
```

A clean installation can run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

## Offline Phase 2 proof

```powershell
python -m src.main data-demo --symbol DEMO
python -m src.main data-status
python -m src.main data-validate --path dataalidated\stock\DEMO.parquet
```

## Download real daily data

Equity/ETF using Yahoo through yfinance:

```powershell
python -m src.main data-download --symbol SPY --asset-class stock --start 2020-01-01 --end 2026-07-22 --provider yahoo
```

Crypto using Yahoo:

```powershell
python -m src.main data-download --symbol BTC-USD --asset-class crypto --start 2020-01-01 --end 2026-07-22 --provider yahoo
```

Crypto using CoinGecko as an independent source:

```powershell
python -m src.main data-download --symbol BTC-USD --asset-class crypto --start 2025-01-01 --end 2025-12-31 --provider coingecko
```

CoinGecko public/demo limits can vary. Yahoo is the default Phase 2 provider; CoinGecko is
included for source diversity and reconciliation work.

## Storage

Validated bars are written to:

```text
data/validated/<asset_class>/<symbol>.parquet
```

Each Parquet file receives a sibling SHA-256 manifest. Generated datasets and reports are
ignored by Git because they are reproducible and may become large.

## Normalized schema

- timestamp (UTC)
- symbol
- asset_class
- open, high, low, close, adj_close
- volume
- dividends, splits
- source
- ingested_at (UTC)

## Phase 2 completion criteria

- Six configuration files validate.
- Offline demo writes and reads Parquet.
- Data quality rejects duplicates, null OHLCV, negative volume, and invalid OHLC.
- Provider tests run without internet by using mocks.
- `pytest`, Ruff, formatting, and mypy pass.
- At least one real SPY and one real BTC-USD dataset download successfully on the user's PC.
- Live trading remains disabled.
