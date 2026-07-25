Phase 13 Ruff B009 fix

Replace:
  src/research/phase13/engine.py

This update removes constant-name getattr calls by using a typed Protocol view over pandas itertuples rows. Runtime behavior is unchanged.
