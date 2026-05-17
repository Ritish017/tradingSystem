from __future__ import annotations

from collections import defaultdict

from app.core.state import STATE
from app.learning.trade_outcome_logger import TradeOutcome


class StrategyScorer:
    def update_weights(self, outcomes: list[TradeOutcome]) -> dict[str, float]:
        pnl_by_strategy: dict[str, float] = defaultdict(float)
        for item in outcomes[-200:]:
            pnl_by_strategy[item.strategy_name] += item.realised_pnl
        if not pnl_by_strategy:
            return {}
        total_positive = sum(max(value, 0.0) for value in pnl_by_strategy.values())
        if total_positive <= 0:
            equal = 1 / len(pnl_by_strategy)
            for name in pnl_by_strategy:
                if name in STATE.strategies:
                    STATE.strategies[name].current_weight = equal
            return {name: equal for name in pnl_by_strategy}
        out: dict[str, float] = {}
        for name, pnl in pnl_by_strategy.items():
            weight = max(pnl, 0.0) / total_positive
            out[name] = weight
            if name in STATE.strategies:
                STATE.strategies[name].current_weight = weight
        return out

