# Phase 1 Success Criteria

Phase 1 passes when:

1. Python 3.11 or 3.12 is used.
2. `pip install -e ".[dev]"` succeeds.
3. `python -m src.main healthcheck` succeeds.
4. `python -m src.main config-validate` succeeds.
5. `pytest` succeeds.
6. `ruff check .` succeeds.
7. `ruff format --check .` succeeds.
8. `mypy src` succeeds.
9. GitHub Actions succeeds.
10. No credential or secret exists in the repository.
