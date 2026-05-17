from __future__ import annotations

from app.core.state import STATE, StrategyState
from app.core.types import OrderRequest
from app.engine.risk_gate import RiskGate


def test_reject_when_daily_loss_breached() -> None:
    gate = RiskGate(max_daily_loss_pct=0.02)
    STATE.daily_realized_pnl = -25_000.0
    order = OrderRequest(client_order_id="o-1", symbol="RELIANCE", side="buy", quantity=1, price=1000)
    decision = gate.evaluate(order)
    assert decision.allowed is False
    assert "daily loss" in decision.reason


def test_reject_when_position_concentration_breached() -> None:
    gate = RiskGate(max_position_concentration_pct=0.20)
    order = OrderRequest(client_order_id="o-2", symbol="TCS", side="buy", quantity=500, price=1000)
    decision = gate.evaluate(order)
    assert decision.allowed is False
    assert "concentration" in decision.reason


def test_reject_when_strategy_circuit_broken() -> None:
    gate = RiskGate(circuit_breaker_losses=3)
    STATE.strategies["mean_reversion"] = StrategyState(
        name="mean_reversion",
        strategy_type="rule_based",
        asset_class="multi",
        consecutive_losses=3,
    )
    order = OrderRequest(
        client_order_id="o-3",
        symbol="BTCUSDT",
        side="sell",
        quantity=1,
        price=100,
        strategy_name="mean_reversion",
    )
    decision = gate.evaluate(order)
    assert decision.allowed is False
    assert "circuit" in decision.reason
    assert STATE.strategies["mean_reversion"].status == "review"

