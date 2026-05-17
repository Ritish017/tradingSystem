from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class MacroAnalystAgent(BaseAgent):
    name = "macro_analyst"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        macro: dict[str, Any] = context.get("macro_data", {})

        rbi_stance = macro.get("rbi_stance", "neutral")  # hawkish/dovish/neutral
        fed_stance = macro.get("fed_stance", "neutral")
        cpi_yoy = float(macro.get("india_cpi_yoy", 5.0))
        gdp_growth = float(macro.get("india_gdp_growth", 6.5))
        usd_inr = float(macro.get("usd_inr", 83.5))
        us_10y_yield = float(macro.get("us_10y_yield", 4.5))

        score = 0.0
        risk = 0.5

        # RBI dovish = bullish for equities
        if rbi_stance == "dovish":
            score += 0.3
        elif rbi_stance == "hawkish":
            score -= 0.3

        # Fed hawkish = bearish for EM
        if fed_stance == "hawkish":
            score -= 0.2
            risk += 0.1
        elif fed_stance == "dovish":
            score += 0.15

        # High inflation = bearish
        if cpi_yoy > 6.0:
            score -= 0.2
            risk += 0.1
        elif cpi_yoy < 4.0:
            score += 0.1

        # Strong GDP = bullish
        if gdp_growth > 7.0:
            score += 0.2
        elif gdp_growth < 5.0:
            score -= 0.2

        # Weak INR = bearish for imports, mixed for IT
        if usd_inr > 86.0:
            score -= 0.1
            risk += 0.05

        # High US yields = bearish for EM flows
        if us_10y_yield > 5.0:
            score -= 0.15
            risk += 0.1

        confidence = min(0.9, 0.5 + abs(score))
        if score > 0.2:
            action = "buy"
        elif score < -0.2:
            action = "sell"
        else:
            action = "hold"

        rationale = (
            f"RBI={rbi_stance}, Fed={fed_stance}, CPI={cpi_yoy}%, "
            f"GDP={gdp_growth}%, USDINR={usd_inr}, US10Y={us_10y_yield}%"
        )
        return self._output(action, confidence, self._clamp(risk), ["NIFTY", "SENSEX", "USDINR"], rationale,
                            {"macro_score": round(score, 3)})
