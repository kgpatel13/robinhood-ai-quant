# ATLAS v16.3.1 compatibility fix

This overlay corrects two integration issues introduced by v16.3:

1. `RobinhoodCryptoReadOnlyAdapter` now declares its fail-closed helper as `NoReturn`, allowing mypy to prove that mutation methods never return.
2. `src/brokers/__init__.py` preserves all legacy broker exports while adding the unified broker manager and Robinhood Crypto adapter exports.

No live order capability is enabled.
