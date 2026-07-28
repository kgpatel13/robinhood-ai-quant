from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.paper_trading.models import PaperAccount


@dataclass(frozen=True)
class DailyPaperReport:
    as_of: datetime
    summary: dict[str, float | int]
    positions: pd.DataFrame
    orders: pd.DataFrame


def build_daily_report(account: PaperAccount, as_of: datetime) -> DailyPaperReport:
    positions = pd.DataFrame(
        [
            {
                "symbol": item.symbol,
                "quantity": item.quantity,
                "average_price": item.average_price,
                "last_price": item.last_price,
                "market_value": item.market_value,
                "unrealized_pnl": item.unrealized_pnl,
                "strategy": item.strategy,
            }
            for item in account.positions.values()
        ]
    )
    orders = pd.DataFrame(
        [
            {
                "order_id": item.request.order_id,
                "symbol": item.request.symbol,
                "side": item.request.side.value,
                "quantity": item.request.quantity,
                "status": item.status.value,
                "reason": item.reason,
                "fill_price": item.fill.price if item.fill is not None else None,
            }
            for item in account.orders
        ]
    )
    return DailyPaperReport(
        as_of=as_of,
        summary={
            "starting_cash": account.starting_cash,
            "cash": account.cash,
            "equity": account.equity,
            "realized_pnl": account.realized_pnl,
            "unrealized_pnl": account.unrealized_pnl,
            "open_positions": len(account.positions),
            "orders": len(account.orders),
        },
        positions=positions,
        orders=orders,
    )
