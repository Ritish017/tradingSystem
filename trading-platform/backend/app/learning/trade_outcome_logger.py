from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TradeOutcome:
    strategy_name: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    holding_period_minutes: int
    realised_pnl: float
    features_at_entry: dict[str, float]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TradeOutcomeLogger:
    def __init__(self) -> None:
        self._outcomes: list[TradeOutcome] = []

    def log(self, outcome: TradeOutcome) -> None:
        self._outcomes.append(outcome)

    def all(self) -> list[TradeOutcome]:
        return list(self._outcomes)

    def as_dicts(self) -> list[dict[str, object]]:
        return [asdict(item) for item in self._outcomes]

