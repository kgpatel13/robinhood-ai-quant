from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from src.execution.calendar import MarketSession
from src.execution.models import AccountSnapshot, OrderReceipt
from src.execution.rebalance import RebalancePlanner
from src.execution.router import OrderRouter
from src.execution.runtime import PaperTradingRuntime, RuntimeCycleResult


@dataclass(frozen=True)
class DataRefreshResult:
    refreshed: bool
    rows_updated: int = 0
    details: str = ""


@dataclass(frozen=True)
class TargetPortfolio:
    weights: Mapping[str, float]
    model_name: str = "unspecified"
    details: str = ""


@dataclass(frozen=True)
class DailyWorkflowConfig:
    min_notional: float = 25.0
    require_market_open: bool = True
    component_name: str = "daily-paper-orchestrator"

    def __post_init__(self) -> None:
        if self.min_notional < 0:
            raise ValueError("min_notional cannot be negative")
        if not self.component_name.strip():
            raise ValueError("component_name is required")


@dataclass(frozen=True)
class DailyWorkflowResult:
    trading_date: date
    status: str
    data_refreshed: bool
    rows_updated: int
    model_name: str
    target_count: int
    planned_orders: int
    accepted_orders: int
    rejected_orders: int
    ignored_symbols: tuple[str, ...]
    receipts: tuple[OrderReceipt, ...]
    runtime: RuntimeCycleResult | None
    account: AccountSnapshot
    details: str = ""


class DataRefresher(Protocol):
    def refresh(self, as_of: datetime) -> DataRefreshResult: ...


class TargetPortfolioProvider(Protocol):
    def generate(self, as_of: datetime, account: AccountSnapshot) -> TargetPortfolio: ...


PriceSnapshotProvider = Callable[[set[str], datetime], Mapping[str, float]]
WorkflowReporter = Callable[[DailyWorkflowResult], None]


class DailyPaperTradingOrchestrator:
    """Run one idempotent data-to-paper-execution workflow per trading day."""

    CHECKPOINT_PREFIX = "daily-paper-workflow"

    def __init__(
        self,
        *,
        runtime: PaperTradingRuntime,
        router: OrderRouter,
        data_refresher: DataRefresher,
        target_provider: TargetPortfolioProvider,
        price_provider: PriceSnapshotProvider,
        session: MarketSession | None = None,
        config: DailyWorkflowConfig | None = None,
        reporter: WorkflowReporter | None = None,
    ) -> None:
        self.runtime = runtime
        self.router = router
        self.data_refresher = data_refresher
        self.target_provider = target_provider
        self.price_provider = price_provider
        self.session = session or runtime.session
        self.config = config or DailyWorkflowConfig()
        self.reporter = reporter

    def run(self, now: datetime, *, force: bool = False) -> DailyWorkflowResult:
        local_now = now.astimezone(ZoneInfo(self.session.timezone))
        trading_date = local_now.date()
        checkpoint_key = f"{self.CHECKPOINT_PREFIX}:{trading_date.isoformat()}"
        account_before = self.runtime.broker.get_account()

        if not self.session.is_trading_day(trading_date):
            return self._finish(
                DailyWorkflowResult(
                    trading_date=trading_date,
                    status="SKIPPED_NON_TRADING_DAY",
                    data_refreshed=False,
                    rows_updated=0,
                    model_name="",
                    target_count=0,
                    planned_orders=0,
                    accepted_orders=0,
                    rejected_orders=0,
                    ignored_symbols=(),
                    receipts=(),
                    runtime=None,
                    account=account_before,
                    details="market calendar marks this date as closed",
                )
            )

        if self.config.require_market_open and not self.session.is_open(now):
            return self._finish(
                DailyWorkflowResult(
                    trading_date=trading_date,
                    status="SKIPPED_MARKET_CLOSED",
                    data_refreshed=False,
                    rows_updated=0,
                    model_name="",
                    target_count=0,
                    planned_orders=0,
                    accepted_orders=0,
                    rejected_orders=0,
                    ignored_symbols=(),
                    receipts=(),
                    runtime=None,
                    account=account_before,
                    details="workflow is configured to submit only during market hours",
                )
            )

        if not force and self.runtime.journal.load_checkpoint(checkpoint_key) is not None:
            return self._finish(
                DailyWorkflowResult(
                    trading_date=trading_date,
                    status="SKIPPED_ALREADY_COMPLETED",
                    data_refreshed=False,
                    rows_updated=0,
                    model_name="",
                    target_count=0,
                    planned_orders=0,
                    accepted_orders=0,
                    rejected_orders=0,
                    ignored_symbols=(),
                    receipts=(),
                    runtime=None,
                    account=account_before,
                    details="a successful workflow checkpoint already exists",
                )
            )

        try:
            refresh = self.data_refresher.refresh(now)
            target = self.target_provider.generate(now, account_before)
            normalized_weights = {
                symbol.upper(): float(weight) for symbol, weight in target.weights.items()
            }
            required_symbols = set(normalized_weights)
            required_symbols.update(position.symbol for position in account_before.positions)
            prices = {
                symbol.upper(): float(price)
                for symbol, price in self.price_provider(required_symbols, now).items()
            }
            plan = RebalancePlanner.plan(
                normalized_weights,
                account_before,
                prices,
                min_notional=self.config.min_notional,
                client_prefix=f"daily:{trading_date.isoformat()}",
            )
            receipts = tuple(self.router.submit(order) for order in plan.orders)
            runtime_result = self.runtime.run_cycle(now)
            account_after = self.runtime.broker.get_account()
            accepted = sum(receipt.accepted for receipt in receipts)
            rejected = len(receipts) - accepted
            status = "COMPLETED" if rejected == 0 else "COMPLETED_WITH_REJECTIONS"
            result = DailyWorkflowResult(
                trading_date=trading_date,
                status=status,
                data_refreshed=refresh.refreshed,
                rows_updated=refresh.rows_updated,
                model_name=target.model_name,
                target_count=len(normalized_weights),
                planned_orders=len(plan.orders),
                accepted_orders=accepted,
                rejected_orders=rejected,
                ignored_symbols=plan.ignored_symbols,
                receipts=receipts,
                runtime=runtime_result,
                account=account_after,
                details="; ".join(part for part in (refresh.details, target.details) if part),
            )
            self.runtime.journal.save_checkpoint(
                checkpoint_key,
                {
                    "status": result.status,
                    "trading_date": trading_date.isoformat(),
                    "planned_orders": result.planned_orders,
                    "accepted_orders": result.accepted_orders,
                    "rejected_orders": result.rejected_orders,
                    "model_name": result.model_name,
                },
            )
            self.runtime.journal.heartbeat(
                self.config.component_name,
                "healthy",
                f"date={trading_date.isoformat()};status={result.status}",
            )
            return self._finish(result)
        except Exception as exc:
            self.runtime.journal.heartbeat(
                self.config.component_name,
                "failed",
                f"date={trading_date.isoformat()};error={type(exc).__name__}:{exc}",
            )
            raise

    def _finish(self, result: DailyWorkflowResult) -> DailyWorkflowResult:
        if self.reporter is not None:
            self.reporter(result)
        return result
