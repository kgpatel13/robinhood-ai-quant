Atlas Phase 9.4-9.6 Ruff/MyPy replacement patch

Replace these files in C:\Projects\robinhood-ai-quant:

src\intelligence\__init__.py
src\intelligence\assistant.py
src\intelligence\explainability.py
src\intelligence\multitimeframe.py

Fixes:
- Exports the Phase 9.4-9.6 public APIs through __all__.
- Wraps all lines to the configured 100-character Ruff limit.
- Removes the unused timeframe loop variable.
- Adds safe object-to-float conversion for assistant records.
- Narrows explanation risks before iteration.
- Preserves existing deterministic assistant and intelligence behavior.

Validation commands:
python -m ruff format .
python -m ruff check . --fix
python -m mypy .
python -m pytest
