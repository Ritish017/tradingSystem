from __future__ import annotations

from app.core.types import AggregatedSignal


class PositionSizer:
    def __init__(self, per_trade_risk_budget: float = 0.01) -> None:
        self.per_trade_risk_budget = per_trade_risk_budget

    def size_for_signal(self, signal: AggregatedSignal, portfolio_value: float, current_price: float) -> float:
        if signal.side == "hold" or current_price <= 0:
            return 0.0
        target_weight = min(max(signal.weighted_strength * signal.weighted_confidence, 0.0), 0.2)
        risk_budget_value = portfolio_value * self.per_trade_risk_budget
        theoretical_value = portfolio_value * target_weight
        order_value = min(theoretical_value, risk_budget_value * 5)
        return max(order_value / current_price, 0.0)

