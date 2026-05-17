from __future__ import annotations

from random import choices

from app.learning.trade_outcome_logger import TradeOutcome


class ReplayBuffer:
    def __init__(self) -> None:
        self._events: list[TradeOutcome] = []

    def extend(self, outcomes: list[TradeOutcome]) -> None:
        self._events.extend(outcomes)

    def sample(self, size: int) -> list[TradeOutcome]:
        if not self._events:
            return []
        weights = []
        for idx, event in enumerate(self._events, start=1):
            recency = idx / len(self._events)
            magnitude = max(abs(event.realised_pnl), 1.0)
            weights.append(recency * magnitude)
        return choices(self._events, weights=weights, k=min(size, len(self._events)))

