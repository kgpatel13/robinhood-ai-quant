# ATLAS v16.2 — Robinhood Crypto API Contract Fix

This build updates the latest project baseline and fixes the live read-only failure caused by comma-joining multiple `symbol` values.

## Changes

- Sends multiple symbols as repeated query parameters:
  - `?symbol=BTC-USD&symbol=ETH-USD&symbol=SOL-USD`
- Signs the exact encoded path and query string sent over HTTP.
- Adds automatic same-host pagination using the API's `next` field.
- Preserves query ordering for deterministic request signing.
- Adds sanitized API errors that include HTTP status and Robinhood error detail.
- Keeps all mutating requests disabled unless explicitly enabled.
- Adds regression tests for repeated symbols and pagination.

## Validation

```powershell
python -m pip install -e ".[dev]"
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest tests\unit\test_robinhood_crypto_foundation.py tests\unit\test_robinhood_crypto_readonly.py -v
python -m pytest
```

## Live read-only check

```powershell
python -m scripts.robinhood_crypto_readonly_check `
  --symbols BTC-USD ETH-USD SOL-USD
```

Order submission remains disabled.
