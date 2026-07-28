from __future__ import annotations

import pandas as pd

from src.paper_trading.models import PaperAccount


def trade_replay(account: PaperAccount) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sequence, result in enumerate(account.orders, start=1):
        fill = result.fill
        rows.append(
            {
                "sequence": sequence,
                "submitted_at": result.request.submitted_at,
                "filled_at": fill.timestamp if fill is not None else None,
                "order_id": result.request.order_id,
                "symbol": result.request.symbol,
                "strategy": result.request.strategy,
                "side": result.request.side.value,
                "quantity": result.request.quantity,
                "status": result.status.value,
                "reason": result.reason,
                "fill_price": fill.price if fill is not None else None,
                "commission": fill.commission if fill is not None else None,
                "slippage_bps": fill.slippage_bps if fill is not None else None,
            }
        )
    return pd.DataFrame(rows)
