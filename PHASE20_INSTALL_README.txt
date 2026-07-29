Atlas v5.0.3 — Phase 20.1–20.3

1. Extract this archive over the existing project directory.
2. Reinstall editable dependencies: pip install -e ".[dev,dashboard]"
3. Run Ruff, MyPy, and PyTest.
4. Optional read-only console:
   streamlit run dashboard/operations_console.py

Live trading remains disabled by default.
