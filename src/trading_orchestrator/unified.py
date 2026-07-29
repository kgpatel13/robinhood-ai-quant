from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Protocol

from src.brokers.base import BrokerAdapter
from src.execution.models import OrderReceipt, OrderRequest
from src.multi_agent_ai import AgentContext, CoordinatedDecision, SupervisorAgent
from src.production_platform import ProductionController, ProductionSnapshot, ServiceHealth

from .integration_models import CycleRequest, CycleResult, CycleStatus, OperationalMode
from .persistence import AtomicCycleStateStore, CycleAuditStore
from .translator import DecisionOrderTranslator


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class UnifiedTradingOrchestrator:
    def __init__(
        self,
        *,
        supervisor: SupervisorAgent,
        production: ProductionController,
        broker: BrokerAdapter,
        services: Callable[[], Iterable[ServiceHealth]],
        audit_store: CycleAuditStore,
        state_store: AtomicCycleStateStore,
        translator: DecisionOrderTranslator | None = None,
        clock: Clock,
    ) -> None:
        self._supervisor = supervisor
        self._production = production
        self._broker = broker
        self._services = services
        self._audit = audit_store
        self._state = state_store
        self._translator = translator or DecisionOrderTranslator()
        self._clock = clock

    def run_cycle(self, request: CycleRequest) -> CycleResult:
        reasons: list[str] = []
        now = self._clock()
        age = (now - request.observation.observed_at).total_seconds()
        if age > request.observation.stale_after_seconds:
            reasons.append("market data is stale")
            return self._finish(request, CycleStatus.BLOCKED, None, None, None, None, reasons)
        if request.mode is OperationalMode.HALTED:
            reasons.append("operational mode is halted")
            return self._finish(request, CycleStatus.BLOCKED, None, None, None, None, reasons)

        production = self._production.evaluate(
            self._services(), reconciliation_clear=request.reconciliation_clear
        )
        if not production.can_trade and request.mode not in {
            OperationalMode.BACKTEST,
            OperationalMode.PAPER,
            OperationalMode.SHADOW,
        }:
            reasons.extend(production.reasons)
            return self._finish(request, CycleStatus.BLOCKED, None, production, None, None, reasons)

        context = AgentContext(
            symbol=request.observation.symbol,
            features=request.observation.features,
            metadata={**request.metadata, "strategy_id": request.strategy_id},
        )
        decision = self._supervisor.decide(context)
        if decision.blocked:
            reasons.extend(decision.explanation or ("agent veto",))
            return self._finish(
                request, CycleStatus.BLOCKED, decision, production, None, None, reasons
            )

        capital_fraction = 1.0
        if request.mode is OperationalMode.CANARY:
            capital_fraction = production.capital_fraction
        order = self._translator.translate(
            decision,
            price=request.observation.price,
            requested_notional=request.requested_notional,
            capital_fraction=capital_fraction,
            client_order_id=request.cycle_id,
        )
        if order is None:
            reasons.append("decision did not produce an executable order")
            return self._finish(
                request, CycleStatus.SKIPPED, decision, production, None, None, reasons
            )

        if request.mode in {OperationalMode.BACKTEST, OperationalMode.SHADOW}:
            reasons.append("order simulated; broker submission disabled for mode")
            return self._finish(
                request, CycleStatus.COMPLETED, decision, production, order, None, reasons
            )

        try:
            receipt = self._broker.submit_order(order)
        except Exception as exc:
            reasons.append(f"broker submission failed: {type(exc).__name__}")
            return self._finish(
                request, CycleStatus.FAILED, decision, production, order, None, reasons
            )
        status = CycleStatus.COMPLETED if receipt.accepted else CycleStatus.FAILED
        if not receipt.accepted:
            reasons.append(receipt.message or "broker rejected order")
        return self._finish(request, status, decision, production, order, receipt, reasons)

    def _finish(
        self,
        request: CycleRequest,
        status: CycleStatus,
        decision: CoordinatedDecision | None,
        production: ProductionSnapshot | None,
        order: OrderRequest | None,
        receipt: OrderReceipt | None,
        reasons: list[str],
    ) -> CycleResult:
        action = getattr(decision, "action", None)
        record: dict[str, object] = {
            "cycle_id": request.cycle_id,
            "symbol": request.observation.symbol,
            "mode": request.mode.value,
            "status": status.value,
            "strategy_id": request.strategy_id,
            "decision": getattr(action, "value", None),
            "confidence": getattr(decision, "confidence", None),
            "reasons": tuple(reasons),
            "recorded_at": self._clock().isoformat(),
            "order_id": getattr(receipt, "order_id", None),
        }
        self._audit.append(record)
        self._state.save(
            {
                "last_cycle_id": request.cycle_id,
                "last_status": status.value,
                "last_symbol": request.observation.symbol,
                "last_order_id": getattr(receipt, "order_id", None),
            }
        )
        return CycleResult(
            cycle_id=request.cycle_id,
            symbol=request.observation.symbol,
            mode=request.mode,
            status=status,
            decision=decision,
            production=production,
            order_request=order,
            order_receipt=receipt,
            reasons=tuple(reasons),
            audit_record=record,
        )
