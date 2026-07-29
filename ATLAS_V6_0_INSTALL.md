# Atlas v6.0.0 Installation

This is a full project snapshot built directly on the user-validated Atlas v5.2.3 baseline.
No existing source package, data asset, script, test, dashboard, document, backup, or historical
artifact was removed.

```powershell
cd C:\Projects\robinhood-ai-quant
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,dashboard]"
python -m ruff check src tests scripts
python -m mypy src
python -m pytest
```

Expected project test count after this release: 412 tests, assuming the validated baseline contained
396 tests.
