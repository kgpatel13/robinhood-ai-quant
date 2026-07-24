Phase 9 quality-gate error fix

Replace these files in the project root:
- src/research/phase9/engine.py
- src/research/phase9/scoring.py
- scripts/phase9_smoke_test.ps1

Fixes:
1. Ruff formatting for Phase 9 Python files.
2. Mypy-safe typed artifact dictionary in engine.py.
3. PowerShell smoke test now stops on any non-zero external command exit code.

After replacement, run:
  python -m pip install -e ".[dev]"
  powershell -ExecutionPolicy Bypass -File .\scripts\phase9_smoke_test.ps1
