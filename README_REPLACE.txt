Phase 11 v0.11.10 quality/runtime fix

Replace these project files while preserving the paths:
- pyproject.toml
- src/research/phase11/model_analysis.py
- src/research/phase11/model_engine.py

Fixes:
- Ruff E501 line-length failures.
- MyPy missing-stub handling for scikit-learn and joblib.
- MyPy variable type collision in model_engine.py.
- pandas-stubs pd.cut overload mismatch.
- Numerical overflow and invalid drawdown warnings in compounded-return calculations.

After replacement, run the commands provided in the ChatGPT response.
