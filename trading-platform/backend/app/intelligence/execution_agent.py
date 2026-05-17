from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class ExecutionAgent(BaseAgent):
    name = "execution_agent"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        exec_ctx: dict[str, Any] = context.get("execution_context", {})

        spread_bps = float(exec_ctx.get("bid_ask_spread_bps", 5.0))
        avg_daily_volume = float(exec_ctx.get("avg_daily_volume", 1_000_000))
        order_size = float(exec_ctx.get("order_size", 10_000))
        market_impact_pct = float(exec_ctx.get("market_impact_pct", 0.1))
        time_of_day = exec_ctx.get("time_of_day", "mid_session")  # open/mid_session/close
        volatility_regime = exec_ctx.get("volatility_regime", "normal")  # low/normal/high

        participation_rate = order_size / avg_daily_volume if avg_daily_volume else 0.01
        risk = 0.3

        # Recommend execution strategy
        if participation_rate > 0.05:
            strategy = "TWAP"
            risk += 0.1
        elif volatility_regime == "high":
            strategy = "VWAP"
            risk += 0.15
        elif spread_bps > 20:
            strategy = "limit_order"
            risk += 0.05
        else:
            strategy = "market_order"

        # Timing
        if time_of_day == "open":
            risk += 0.1  # higher volatility at open
        elif time_of_day == "close":
            risk += 0.05

        slippage_est_bps = spread_bps / 2 + market_impact_pct * 100 * participation_rate * 10

        rationale = (
            f"strategy={strategy}, spread={spread_bps:.1f}bps, "
            f"participation={participation_rate:.2%}, slippage_est={slippage_est_bps:.1f}bps"
        )
        return self._output("hold", 0.8, self._clamp(risk), [], rationale,
                            {"recommended_strategy": strategy, "slippage_est_bps": round(slippage_est_bps, 2),
                             "participation_rate": round(participation_rate, 4)})
