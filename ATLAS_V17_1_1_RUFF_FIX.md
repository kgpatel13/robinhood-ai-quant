# ATLAS v17.1.1 Ruff Fix

Splits the long SQLite query string in `src/trading_ledger/sqlite.py` so Ruff E501 passes.
No runtime behavior changes.
