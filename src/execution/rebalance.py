from __future__ import annotations

from dataclasses import dataclass

from src.execution.models import AccountSnapshot, OrderRequest, OrderSide


@dataclass(frozen=True)
class RebalancePlan:
    orders: tuple[OrderRequest, ...]
    ignored_symbols: tuple[str, ...]


class RebalancePlanner:
    @staticmethod
    def plan(
        target_weights: dict[str, float],
        account: AccountSnapshot,
        prices: dict[str, float],
        *,
        min_notional: float = 1.0,
        client_prefix: str = "rebalance",
    ) -> RebalancePlan:
        if min_notional < 0:
            raise ValueError("min_notional cannot be negative")
        total_weight = sum(target_weights.values())
        if any(weight < 0 for weight in target_weights.values()) or total_weight > 1.0 + 1e-9:
            raise ValueError("target weights must be non-negative and sum to at most one")

        current = {position.symbol: position.market_value for position in account.positions}
        symbols = sorted(set(current) | {symbol.upper() for symbol in target_weights})
        sells: list[OrderRequest] = []
        buys: list[OrderRequest] = []
        ignored: list[str] = []
        for symbol in symbols:
            price = prices.get(symbol)
            if price is None or price <= 0:
                ignored.append(symbol)
                continue
            target_value = account.equity * target_weights.get(symbol, 0.0)
            difference = target_value - current.get(symbol, 0.0)
            if abs(difference) < min_notional:
                continue
            side = OrderSide.BUY if difference > 0 else OrderSide.SELL
            request = OrderRequest(
                symbol=symbol,
                quantity=abs(difference) / price,
                side=side,
                client_order_id=f"{client_prefix}:{symbol}:{side.value}",
            )
            (buys if side is OrderSide.BUY else sells).append(request)
        return RebalancePlan(tuple(sells + buys), tuple(ignored))
