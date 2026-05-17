from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from threading import Lock

from app.core.types import ExecutionFill, OrderRequest, Signal


@dataclass
class StrategyState:
    name: str
    strategy_type: str
    asset_class: str
    status: str = "paper"
    allocated_capital: float = 0.0
    current_weight: float = 0.0
    consecutive_losses: int = 0
    rolling_sharpe_30d: float = 0.0


@dataclass
class PositionState:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    unrealized_pnl: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EngineState:
    capital: float = 1_000_000.0
    gross_exposure: float = 0.0
    fo_margin_utilisation: float = 0.0
    daily_realized_pnl: float = 0.0
    trading_halted: bool = False
    halted_reason: str | None = None
    active_day: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    orders: dict[str, OrderRequest] = field(default_factory=dict)
    order_status: dict[str, str] = field(default_factory=dict)
    fills: list[ExecutionFill] = field(default_factory=list)
    positions: dict[str, PositionState] = field(default_factory=dict)
    signals: list[Signal] = field(default_factory=list)
    strategies: dict[str, StrategyState] = field(default_factory=dict)
    retraining_runs: list[dict[str, float | str]] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def reset_if_new_day(self) -> None:
        utc_day = datetime.now(timezone.utc).date()
        if utc_day != self.active_day:
            self.active_day = utc_day
            self.daily_realized_pnl = 0.0
            self.trading_halted = False
            self.halted_reason = None


STATE = EngineState()

