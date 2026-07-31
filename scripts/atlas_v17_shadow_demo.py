from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.execution.models import OrderRequest, OrderSide
from src.shadow_trading import ShadowExecutionConfig, ShadowExecutionEngine
from src.trading_ledger import SQLiteTradingLedger, build_performance_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="ATLAS v17 persistent shadow-trading demo")
    parser.add_argument("--db", type=Path, default=Path("data/atlas_v17_shadow.db"))
    parser.add_argument("--symbol", default="BTC-USD")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--side", choices=("buy", "sell"), default="buy")
    parser.add_argument("--starting-cash", type=float, default=100_000.0)
    args = parser.parse_args()

    ledger = SQLiteTradingLedger(args.db, starting_cash=args.starting_cash)
    engine = ShadowExecutionEngine(
        ledger=ledger,
        quote_provider=lambda _symbol: args.price,
        config=ShadowExecutionConfig(max_order_notional=10_000.0),
    )
    receipt = engine.submit(
        OrderRequest(
            symbol=args.symbol,
            quantity=args.quantity,
            side=OrderSide(args.side),
        ),
        strategy="cli-demo",
    )
    summary = ledger.summary({args.symbol.upper(): args.price})
    performance = build_performance_snapshot(summary)
    print(
        json.dumps(
            {
                "receipt": {
                    "order_id": receipt.order_id,
                    "accepted": receipt.accepted,
                    "message": receipt.message,
                },
                "summary": {
                    "cash": summary.cash,
                    "market_value": summary.market_value,
                    "equity": summary.equity,
                    "realized_pnl": summary.realized_pnl,
                    "unrealized_pnl": summary.unrealized_pnl,
                    "orders": summary.order_count,
                    "fills": summary.fill_count,
                },
                "performance": {
                    "net_pnl": performance.net_pnl,
                    "return_pct": performance.return_pct,
                    "cash_utilization_pct": performance.cash_utilization_pct,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
