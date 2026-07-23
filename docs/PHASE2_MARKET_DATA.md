# Phase 2 — Market Data Architecture

## Delivered

- Provider protocol decoupled from brokers
- Yahoo Finance adapter for equity/ETF and crypto daily bars
- CoinGecko adapter for crypto source diversification
- Canonical UTC OHLCV schema
- Parquet storage with deterministic paths
- Upsert and duplicate-date replacement
- SHA-256 sidecar manifests
- Data-quality validation
- Dataset catalog/status command
- Fully offline demo and mocked provider tests

## Known limitations

- Yahoo/yfinance is suitable for research and education but is not an exchange-grade feed.
- CoinGecko market-chart data is aggregated into daily OHLC from returned samples; it is a
  secondary validation source, not the primary execution price source.
- Corporate-action verification against a second equity source is deferred.
- Intraday data, delisted-security survivorship handling, and point-in-time universe data are
  deferred to later research-hardening work.

## Safety

No module imports or calls a Robinhood trading interface. No order model exists in Phase 2.
