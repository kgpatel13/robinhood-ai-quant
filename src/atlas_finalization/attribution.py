from __future__ import annotations

from src.atlas_finalization.models import TradeAttribution, TradeAttributionInput


class PerformanceAttributionEngine:
    @staticmethod
    def attribute(item: TradeAttributionInput) -> TradeAttribution:
        cost_drag = item.fees + item.slippage
        net_pnl = item.gross_pnl - cost_drag
        weights = (item.strategy_weight, item.agent_weight, item.sizing_weight)
        total_weight = sum(max(value, 0.0) for value in weights)
        if total_weight == 0:
            strategy_share, agent_share, sizing_share = 1.0, 0.0, 0.0
        else:
            strategy_share, agent_share, sizing_share = (
                max(value, 0.0) / total_weight for value in weights
            )
        return TradeAttribution(
            trade_id=item.trade_id,
            net_pnl=net_pnl,
            strategy_contribution=net_pnl * strategy_share,
            agent_contribution=net_pnl * agent_share,
            sizing_contribution=net_pnl * sizing_share,
            cost_drag=cost_drag,
        )
