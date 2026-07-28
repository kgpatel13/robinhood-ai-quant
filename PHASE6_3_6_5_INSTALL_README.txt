ATLAS PHASE 6.3-6.5 CONTROL CENTER
===================================

Included:
- Multi-symbol intraday opportunity ranking
- Explainable candidate rejection reasons
- Portfolio exposure, sector, trade-count, daily-loss and cooldown safeguards
- Persistent JSON paper-session state with atomic writes and restart recovery
- Named JSON configuration profiles
- Streamlit Atlas Control Center dashboard
- Strict PAPER ONLY configuration enforcement

Install dashboard dependency:
  python -m pip install -e ".[dev,dashboard]"

Run validation:
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest

Launch dashboard:
  python -m streamlit run dashboard/app.py

The dashboard demonstration uses deterministic synthetic bars. It does not connect to Robinhood,
does not submit orders, and cannot enable live trading.
