ATLAS PHASE 7.3-7.8 — REAL-MARKET PAPER TRADING
================================================

Version: 3.7.8

This release adds:
- Yahoo minute-quote adapter (real market data; delayed/availability limitations apply)
- Bid/ask spread approximation and configurable slippage
- Restart-safe JSON paper account persistence
- Simulated buy/sell order lifecycle
- Duplicate order ID protection
- Cash, position, and maximum-order-notional validation
- Mark-to-market equity and unrealized P&L
- Stale/missing quote session halt
- Session start/pause/resume/stop controls in service layer
- End-of-day flattening service
- Dashboard Real-Market Paper tab
- Paper order journal CSV export
- Daily paper account reporting

SAFETY BOUNDARY
---------------
MODE: PAPER ONLY
LIVE BROKER: DISABLED
ORDER SUBMISSION: UNAVAILABLE

INSTALL
-------
python -m pip install -e ".[dev,dashboard]"

VALIDATE
--------
python -m ruff format .
python -m ruff check .
python -m mypy .
python -m pytest

RUN DASHBOARD
-------------
python -m streamlit run dashboard/app.py

Then open the "Real-Market Paper" tab and click "Refresh quotes".
Yahoo data is suitable for development and research validation, not a production-grade low-latency feed.
