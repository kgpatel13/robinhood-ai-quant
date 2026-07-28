Atlas Phase 7.3-7.8 validation patch

Replace the included files at the matching paths in the project root.

Fixes:
- Ruff E501 line-length issues in dashboard/app.py
- Ruff I001 import ordering issues
- Ruff UP017 datetime.UTC modernization in tests
- MyPy narrowing for serialized positions in PaperAccountStore
- Dashboard timestamps displayed in America/New_York (ET)

Timezone policy:
- Internal timestamps remain UTC for durable storage and comparisons.
- Market-session rules and dashboard display use America/New_York.
- America/New_York automatically handles EST in winter and EDT in summer.

After replacement run:
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest
