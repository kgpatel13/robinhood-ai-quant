from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.paper_trading.models import (
    MarketQuote,
    PaperAccount,
    PaperFill,
    PaperOrderRequest,
    PaperOrderResult,
    PaperOrderSide,
    PaperOrderStatus,
    PaperPosition,
)


@dataclass(frozen=True)
class PaperBrokerConfig:
    commission_per_order: float = 0.0
    slippage_bps: float = 2.0
    maximum_order_notional: float = 25_000.0


class PaperBroker:
    def __init__(self, account: PaperAccount, config: PaperBrokerConfig | None = None) -> None:
        self.account = account
        self.config = config or PaperBrokerConfig()
        self._processed_ids: set[str] = {item.request.order_id for item in account.orders}

    def submit(self, request: PaperOrderRequest, quote: MarketQuote) -> PaperOrderResult:
        if request.order_id in self._processed_ids:
            return self._reject(request, "duplicate order id")
        self._processed_ids.add(request.order_id)
        if request.quantity <= 0:
            return self._reject(request, "quantity must be positive")
        base_price = quote.ask if request.side == PaperOrderSide.BUY else quote.bid
        direction = 1.0 if request.side == PaperOrderSide.BUY else -1.0
        fill_price = base_price * (1.0 + direction * self.config.slippage_bps / 10_000.0)
        notional = fill_price * request.quantity
        if notional > self.config.maximum_order_notional:
            return self._reject(request, "maximum paper order notional exceeded")
        if request.limit_price is not None:
            if request.side == PaperOrderSide.BUY and fill_price > request.limit_price:
                return self._reject(request, "buy limit not marketable")
            if request.side == PaperOrderSide.SELL and fill_price < request.limit_price:
                return self._reject(request, "sell limit not marketable")
        if request.side == PaperOrderSide.BUY:
            required_cash = notional + self.config.commission_per_order
            if required_cash > self.account.cash:
                return self._reject(request, "insufficient paper cash")
            self.account.cash -= required_cash
            existing = self.account.positions.get(request.symbol)
            if existing is None:
                self.account.positions[request.symbol] = PaperPosition(
                    symbol=request.symbol,
                    quantity=request.quantity,
                    average_price=fill_price,
                    strategy=request.strategy,
                    opened_at=request.submitted_at,
                    last_price=quote.last,
                )
            else:
                total_quantity = existing.quantity + request.quantity
                existing.average_price = (
                    existing.average_price * existing.quantity + fill_price * request.quantity
                ) / total_quantity
                existing.quantity = total_quantity
                existing.last_price = quote.last
        else:
            existing = self.account.positions.get(request.symbol)
            if existing is None or request.quantity > existing.quantity:
                return self._reject(request, "insufficient paper position")
            proceeds = notional - self.config.commission_per_order
            self.account.cash += proceeds
            self.account.realized_pnl += request.quantity * (fill_price - existing.average_price)
            existing.quantity -= request.quantity
            existing.last_price = quote.last
            if existing.quantity == 0:
                del self.account.positions[request.symbol]
        fill = PaperFill(
            order_id=request.order_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=fill_price,
            timestamp=datetime.now(UTC),
            commission=self.config.commission_per_order,
            slippage_bps=self.config.slippage_bps,
        )
        result = PaperOrderResult(request, PaperOrderStatus.FILLED, "filled", fill)
        self.account.orders.append(result)
        return result

    def mark_to_market(self, quotes: dict[str, MarketQuote]) -> None:
        for symbol, position in self.account.positions.items():
            quote = quotes.get(symbol)
            if quote is not None:
                position.last_price = quote.last

    def flatten_all(
        self, quotes: dict[str, MarketQuote], timestamp: datetime
    ) -> list[PaperOrderResult]:
        results: list[PaperOrderResult] = []
        for symbol, position in list(self.account.positions.items()):
            quote = quotes.get(symbol)
            if quote is None:
                continue
            request = PaperOrderRequest(
                order_id=f"flatten-{symbol}-{timestamp.isoformat()}",
                symbol=symbol,
                side=PaperOrderSide.SELL,
                quantity=position.quantity,
                submitted_at=timestamp,
                strategy=position.strategy,
            )
            results.append(self.submit(request, quote))
        return results

    def _reject(self, request: PaperOrderRequest, reason: str) -> PaperOrderResult:
        result = PaperOrderResult(request, PaperOrderStatus.REJECTED, reason)
        self.account.orders.append(result)
        return result
