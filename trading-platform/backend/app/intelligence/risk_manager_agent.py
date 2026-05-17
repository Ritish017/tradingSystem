from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class RiskManagerAgent(BaseAgent):
    name = "risk_manager"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        portfolio: dict[str, Any] = context.get("portfolio_state", {})

        gross_exposure = float(portfolio.get("gross_exposure_pct", 50.0))
        daily_pnl_pct = float(portfolio.get("daily_pnl_pct", 0.0))
        max_dd_pct = float(portfolio.get("max_drawdown_pct", 5.0))
        corr_breakdown = bool(portfolio.get("correlation_breakdown", False))
        vix_level = float(portfolio.get("vix", 15.0))
        india_vix = float(portfolio.get("india_vix", 14.0))

        risk = 0.3
        action = "hold"
        rationale_parts = []

        if daily_pnl_pct < -1.5:
            risk += 0.3
            action = "sell"
            rationale_parts.append(f"daily_loss={daily_pnl_pct:.1f}%")

        if gross_exposure > 90:
            risk += 0.2
            action = "sell"
            rationale_parts.append(f"overexposed={gross_exposure:.0f}%")

        if max_dd_pct > 8:
            risk += 0.25
            action = "sell"
            rationale_parts.append(f"drawdown={max_dd_pct:.1f}%")

        if corr_breakdown:
            risk += 0.15
            rationale_parts.append("correlation_breakdown")

        if vix_level > 30 or india_vix > 25:
            risk += 0.15
            rationale_parts.append(f"high_vix={vix_level:.0f}/{india_vix:.0f}")

        confidence = min(0.95, 0.5 + risk * 0.5)
        rationale = ", ".join(rationale_parts) if rationale_parts else "risk_within_limits"

        return self._output(action, confidence, self._clamp(risk), [], rationale,
                            {"gross_exposure": gross_exposure, "daily_pnl_pct": daily_pnl_pct})
