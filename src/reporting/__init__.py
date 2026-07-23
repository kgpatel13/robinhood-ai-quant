"""Reporting helpers configured for headless chart rendering."""

import matplotlib

matplotlib.use("Agg", force=True)

from src.reporting.backtest_report import write_backtest_report
from src.reporting.portfolio_report import write_portfolio_report

__all__ = ["write_backtest_report", "write_portfolio_report"]
