from __future__ import annotations

from collections import Counter

from src.broker_reconciliation.models import (
    DiscrepancyType,
    ReconciliationDecision,
    ReconciliationDiscrepancy,
    ReconciliationPolicy,
    ReconciliationReport,
)
from src.execution.models import AccountSnapshot, OrderSnapshot


class BrokerReconciliationEngine:
    """Compares Atlas state with broker-reported account and order state."""

    def __init__(self, policy: ReconciliationPolicy | None = None) -> None:
        self._policy = policy or ReconciliationPolicy()

    def reconcile(
        self,
        local_account: AccountSnapshot,
        broker_account: AccountSnapshot,
        local_orders: tuple[OrderSnapshot, ...] = (),
        broker_orders: tuple[OrderSnapshot, ...] = (),
    ) -> ReconciliationReport:
        discrepancies: list[ReconciliationDiscrepancy] = []
        self._compare_cash(local_account, broker_account, discrepancies)
        self._compare_positions(local_account, broker_account, discrepancies)
        self._compare_orders(local_orders, broker_orders, discrepancies)
        self._find_duplicates(broker_orders, discrepancies)
        score = sum(item.severity for item in discrepancies)
        if score >= self._policy.halt_score:
            decision = ReconciliationDecision.HALT
        elif score >= self._policy.warning_score:
            decision = ReconciliationDecision.WARNING
        else:
            decision = ReconciliationDecision.MATCHED
        return ReconciliationReport(decision, score, tuple(discrepancies))

    def _compare_cash(
        self,
        local: AccountSnapshot,
        broker: AccountSnapshot,
        output: list[ReconciliationDiscrepancy],
    ) -> None:
        difference = abs(local.cash - broker.cash)
        if difference > self._policy.cash_tolerance:
            output.append(
                ReconciliationDiscrepancy(
                    DiscrepancyType.CASH,
                    "cash",
                    f"cash differs by {difference:.2f}",
                    2,
                )
            )

    def _compare_positions(
        self,
        local: AccountSnapshot,
        broker: AccountSnapshot,
        output: list[ReconciliationDiscrepancy],
    ) -> None:
        local_map = {position.symbol: position for position in local.positions}
        broker_map = {position.symbol: position for position in broker.positions}
        for symbol in sorted(local_map.keys() | broker_map.keys()):
            local_position = local_map.get(symbol)
            broker_position = broker_map.get(symbol)
            if local_position is None:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.POSITION_MISSING_LOCAL,
                        symbol,
                        "position exists at broker but not locally",
                        2,
                    )
                )
            elif broker_position is None:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.POSITION_MISSING_BROKER,
                        symbol,
                        "position exists locally but not at broker",
                        2,
                    )
                )
            elif abs(local_position.quantity - broker_position.quantity) > (
                self._policy.quantity_tolerance
            ):
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.POSITION_QUANTITY,
                        symbol,
                        "position quantity differs",
                        2,
                    )
                )

    @staticmethod
    def _compare_orders(
        local: tuple[OrderSnapshot, ...],
        broker: tuple[OrderSnapshot, ...],
        output: list[ReconciliationDiscrepancy],
    ) -> None:
        local_map = {order.order_id: order for order in local}
        broker_map = {order.order_id: order for order in broker}
        for order_id in sorted(local_map.keys() | broker_map.keys()):
            local_order = local_map.get(order_id)
            broker_order = broker_map.get(order_id)
            if local_order is None:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.ORDER_MISSING_LOCAL,
                        order_id,
                        "order exists at broker but not locally",
                    )
                )
            elif broker_order is None:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.ORDER_MISSING_BROKER,
                        order_id,
                        "order exists locally but not at broker",
                    )
                )
            elif local_order.status is not broker_order.status:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.ORDER_STATUS,
                        order_id,
                        "order status differs",
                    )
                )

    @staticmethod
    def _find_duplicates(
        broker_orders: tuple[OrderSnapshot, ...],
        output: list[ReconciliationDiscrepancy],
    ) -> None:
        counts = Counter(order.request.client_order_id for order in broker_orders)
        for client_order_id, count in sorted(counts.items()):
            if count > 1:
                output.append(
                    ReconciliationDiscrepancy(
                        DiscrepancyType.DUPLICATE_CLIENT_ORDER_ID,
                        client_order_id,
                        f"client order id appears {count} times",
                        3,
                    )
                )
