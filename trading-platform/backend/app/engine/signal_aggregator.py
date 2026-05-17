from __future__ import annotations

from collections import defaultdict

from app.core.state import STATE
from app.core.types import AggregatedSignal, Signal


class SignalAggregator:
    def aggregate(self, symbol: str, signals: list[Signal]) -> AggregatedSignal:
        if not signals:
            return AggregatedSignal(symbol=symbol, side="hold", weighted_strength=0.0, weighted_confidence=0.0, votes=[])

        side_scores: dict[str, float] = defaultdict(float)
        confidence_weight = 0.0
        for signal in signals:
            strategy = STATE.strategies.get(signal.strategy_name)
            weight = strategy.current_weight if strategy is not None and strategy.current_weight > 0 else 1.0
            side_scores[signal.side] += signal.strength * weight
            confidence_weight += signal.confidence * weight

        buy = side_scores.get("buy", 0.0)
        sell = side_scores.get("sell", 0.0)
        hold = side_scores.get("hold", 0.0)
        if buy > max(sell, hold):
            side = "buy"
            strength = buy
        elif sell > max(buy, hold):
            side = "sell"
            strength = sell
        else:
            side = "hold"
            strength = hold
        return AggregatedSignal(
            symbol=symbol,
            side=side,
            weighted_strength=strength / max(len(signals), 1),
            weighted_confidence=confidence_weight / max(len(signals), 1),
            votes=signals,
        )

