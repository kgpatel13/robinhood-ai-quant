from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.execution.calendar import MarketSession
from src.execution.paper import PaperBroker
from src.execution.persistence import ExecutionJournal


@dataclass(frozen=True)
class RuntimeCycleResult:
    market_open: bool
    fills_processed: int
    checkpoint_written: bool


class PaperTradingRuntime:
    CHECKPOINT_KEY = "paper_broker_state"

    def __init__(
        self,
        broker: PaperBroker,
        journal: ExecutionJournal,
        *,
        session: MarketSession | None = None,
    ) -> None:
        self.broker = broker
        self.journal = journal
        self.session = session or MarketSession()

    def recover(self) -> bool:
        state = self.journal.load_checkpoint(self.CHECKPOINT_KEY)
        if state is None:
            return False
        self.broker.restore_state(state)
        self.journal.heartbeat("paper-runtime", "recovered")
        return True

    def checkpoint(self) -> None:
        self.journal.save_checkpoint(self.CHECKPOINT_KEY, self.broker.export_state())
        for order in self.broker.list_orders():
            self.journal.record_order(order)
        for fill in self.broker.list_fills():
            self.journal.record_fill(fill)
        self.journal.record_account_snapshot(self.broker.get_account())

    def run_cycle(self, now: datetime) -> RuntimeCycleResult:
        market_open = self.session.is_open(now)
        fills = self.broker.process_open_orders() if market_open else 0
        self.checkpoint()
        self.journal.heartbeat(
            "paper-runtime",
            "healthy",
            f"market_open={market_open};fills_processed={fills}",
        )
        return RuntimeCycleResult(market_open, fills, True)

    def health(self) -> dict[str, Any]:
        account = self.broker.get_account()
        return {
            "broker": self.broker.name,
            "cash": account.cash,
            "equity": account.equity,
            "orders": len(self.broker.list_orders()),
            "fills": len(self.broker.list_fills()),
        }
