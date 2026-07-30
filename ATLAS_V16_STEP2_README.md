# ATLAS v16 Step 2 — Robinhood Crypto Read-Only Integration

This overlay adds typed read-only Robinhood Crypto access on top of Step 1.

Included:

- account status retrieval
- holdings retrieval and filtering
- trading-pair discovery
- best bid/ask retrieval
- estimated-price retrieval
- order history and single-order status retrieval
- bounded retries for read-only HTTP methods
- sanitized diagnostics
- no order creation, cancellation, or mutation methods

## Install

Extract into the repository root with overwrite enabled, then run:

```powershell
python -m pip install -e ".[dev]"
python -m ruff format .
python -m ruff check . --fix
python -m mypy src
python -m pytest tests\unit\test_robinhood_crypto_foundation.py tests\unit\test_robinhood_crypto_readonly.py -v
python -m pytest
```

## First authenticated read-only test

Set credentials only in the current PowerShell session or a non-committed `.env`/secret path. Then run:

```powershell
python -m scripts.robinhood_crypto_readonly_check --symbols BTC-USD ETH-USD SOL-USD
```

The output is deliberately sanitized. Live order submission remains unavailable in this step.
