from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class PortfolioManagerAgent(BaseAgent):
    name = "portfolio_manager"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        portfolio: dict[str, Any] = context.get("portfolio_state", {})
        agent_outputs: list[dict[str, Any]] = context.get("agent_outputs", [])

        capital = float(portfolio.get("capital", 1_000_000))
        cash_pct = float(portfolio.get("cash_pct", 30.0))
        equity_pct = float(portfolio.get("equity_pct", 50.0))
        commodity_pct = float(portfolio.get("commodity_pct", 10.0))
        crypto_pct = float(portfolio.get("crypto_pct", 10.0))

        # Aggregate agent votes
        buy_votes = sum(1 for a in agent_outputs if a.get("action") == "buy")
        sell_votes = sum(1 for a in agent_outputs if a.get("action") == "sell")
        total_votes = len(agent_outputs) or 1

        avg_confidence = sum(a.get("confidence", 0.5) for a in agent_outputs) / total_votes
        avg_risk = sum(a.get("risk", 0.5) for a in agent_outputs) / total_votes

        # Rebalancing signals
        rebalance_needed = False
        rationale_parts = []

        if cash_pct < 10:
            rebalance_needed = True
            rationale_parts.append("low_cash")
        if avg_risk > 0.7:
            rebalance_needed = True
            rationale_parts.append("high_risk_environment")

        if buy_votes / total_votes > 0.6 and avg_risk < 0.5:
            action = "buy"
        elif sell_votes / total_votes > 0.5 or avg_risk > 0.65:
            action = "sell"
        else:
            action = "hold"

        rationale = f"votes={buy_votes}B/{sell_votes}S, avg_risk={avg_risk:.2f}, rebalance={rebalance_needed}"
        return self._output(action, avg_confidence, avg_risk, [], rationale,
                            {"rebalance_needed": rebalance_needed, "buy_votes": buy_votes, "sell_votes": sell_votes})
