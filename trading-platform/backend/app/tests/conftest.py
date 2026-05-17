from __future__ import annotations

import pytest

from app.core.state import STATE


@pytest.fixture(autouse=True)
def reset_state() -> None:
    STATE.orders.clear()
    STATE.order_status.clear()
    STATE.fills.clear()
    STATE.positions.clear()
    STATE.signals.clear()
    STATE.strategies.clear()
    STATE.retraining_runs.clear()
    STATE.daily_realized_pnl = 0.0
    STATE.gross_exposure = 0.0
    STATE.fo_margin_utilisation = 0.0
    STATE.trading_halted = False
    STATE.halted_reason = None
    STATE.capital = 1_000_000.0

