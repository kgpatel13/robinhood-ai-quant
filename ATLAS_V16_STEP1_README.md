# ATLAS v16 — Step 1: Robinhood Crypto security foundation

This step adds only the credential loader, Ed25519 request signer, signed HTTP transport,
and safety configuration. It does not add strategy routing or enable live orders.

## Required environment variables

Preferred file-based private-key configuration:

```powershell
$env:ROBINHOOD_CRYPTO_API_KEY="your-api-key"
$env:ROBINHOOD_CRYPTO_PRIVATE_KEY_PATH="C:\secure\robinhood_crypto_private.key"
```

The key file must contain only the base64 private key generated for Robinhood Crypto.
Do not configure `ROBINHOOD_CRYPTO_PRIVATE_KEY` when the path variable is set.

## Install and validate

```powershell
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m mypy src
python -m pytest tests/unit/test_robinhood_crypto_foundation.py -v
python -m pytest
```

## Safety status

`RobinhoodCryptoClientConfig.order_submission_enabled` defaults to `false`. Any request
marked `mutating=True` fails closed until a later testing phase explicitly enables it.
