from __future__ import annotations

import pandas as pd

from src.paper_trading.models import PaperAccount, PaperOrderSide, PaperOrderStatus


def strategy_attribution(account: PaperAccount) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for order in account.orders:
        if order.status != PaperOrderStatus.FILLED or order.fill is None:
            continue
        rows.append(
            {
                "strategy": order.request.strategy,
                "symbol": order.request.symbol,
                "side": order.request.side.value,
                "quantity": order.request.quantity,
                "notional": order.fill.price * order.fill.quantity,
                "commission": order.fill.commission,
                "signed_flow": (
                    -order.fill.price * order.fill.quantity
                    if order.request.side == PaperOrderSide.BUY
                    else order.fill.price * order.fill.quantity
                ),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["strategy", "orders", "symbols", "gross_notional", "commissions", "net_flow"]
        )
    frame = pd.DataFrame(rows)
    return (
        frame.groupby("strategy", as_index=False)
        .agg(
            orders=("symbol", "size"),
            symbols=("symbol", "nunique"),
            gross_notional=("notional", "sum"),
            commissions=("commission", "sum"),
            net_flow=("signed_flow", "sum"),
        )
        .sort_values("gross_notional", ascending=False)
    )


def position_exposure(account: PaperAccount) -> pd.DataFrame:
    rows = [
        {
            "symbol": item.symbol,
            "strategy": item.strategy,
            "quantity": item.quantity,
            "average_price": item.average_price,
            "last_price": item.last_price,
            "market_value": item.market_value,
            "unrealized_pnl": item.unrealized_pnl,
            "portfolio_weight": item.market_value / account.equity if account.equity else 0.0,
        }
        for item in account.positions.values()
    ]
    return pd.DataFrame(rows)
