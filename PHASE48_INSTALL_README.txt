Phase 4.8 - Broker and Paper Trading Foundation

Added:
- BrokerManager
- expanded broker protocol and execution domain models
- PaperBroker with cash/position accounting
- OrderStateMachine
- OrderRouter with retry and duplicate-order prevention
- ExecutionMonitor
- PortfolioSync reconciliation
- market and resting limit orders
- cancel and cancel/replace foundation

Safety boundary:
- paper-only
- no Robinhood, Alpaca, or Interactive Brokers network adapter
- no live credentials or live order submission

Validation (Python 3.12):
  pip install -e ".[dev]"
  python -m ruff format .
  python -m ruff check .
  python -m mypy .
  python -m pytest
