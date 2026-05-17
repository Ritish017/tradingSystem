from __future__ import annotations

from app.core.state import STATE
from app.core.types import OrderRequest, RiskDecision


class RiskGate:
    def __init__(
        self,
        max_daily_loss_pct: float = 0.02,
        max_position_concentration_pct: float = 0.20,
        max_gross_exposure_pct: float = 1.0,
        max_fo_margin_utilisation_pct: float = 0.60,
        circuit_breaker_losses: int = 3,
    ) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_concentration_pct = max_position_concentration_pct
        self.max_gross_exposure_pct = max_gross_exposure_pct
        self.max_fo_margin_utilisation_pct = max_fo_margin_utilisation_pct
        self.circuit_breaker_losses = circuit_breaker_losses

    def evaluate(self, order: OrderRequest) -> RiskDecision:
        STATE.reset_if_new_day()
        if STATE.trading_halted:
            return RiskDecision(allowed=False, reason=f"system halted: {STATE.halted_reason or 'manual'}")

        daily_loss_limit = -STATE.capital * self.max_daily_loss_pct
        if STATE.daily_realized_pnl <= daily_loss_limit:
            STATE.trading_halted = True
            STATE.halted_reason = "daily-loss-limit"
            return RiskDecision(allowed=False, reason="max daily loss breached")

        pos = STATE.positions.get(order.symbol)
        current_notional = abs(pos.quantity * pos.avg_price) if pos is not None else 0.0
        proposed_notional = current_notional + abs(order.quantity * order.price)
        concentration = proposed_notional / max(STATE.capital, 1e-9)
        if concentration > self.max_position_concentration_pct:
            return RiskDecision(allowed=False, reason="position concentration breach")

        projected_gross = STATE.gross_exposure + abs(order.quantity * order.price)
        if projected_gross / max(STATE.capital, 1e-9) > self.max_gross_exposure_pct:
            return RiskDecision(allowed=False, reason="gross exposure breach")

        if order.symbol.endswith("FUT") or order.symbol.endswith("OPT"):
            if STATE.fo_margin_utilisation > self.max_fo_margin_utilisation_pct:
                return RiskDecision(allowed=False, reason="F&O margin utilisation breach")

        if order.strategy_name is not None:
            strategy = STATE.strategies.get(order.strategy_name)
            if strategy is not None and strategy.consecutive_losses >= self.circuit_breaker_losses:
                strategy.status = "review"
                return RiskDecision(allowed=False, reason="strategy circuit broken")

        return RiskDecision(allowed=True, reason="ok")

