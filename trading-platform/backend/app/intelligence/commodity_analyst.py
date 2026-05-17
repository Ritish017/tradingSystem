from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class CommodityAnalystAgent(BaseAgent):
    name = "commodity_analyst"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        comm: dict[str, Any] = context.get("commodity_data", {})

        gold_mcx = float(comm.get("gold_mcx_per10g", 72000))
        gold_comex = float(comm.get("gold_comex_usd_oz", 2300))
        silver_mcx = float(comm.get("silver_mcx_per_kg", 85000))
        usd_inr = float(comm.get("usd_inr", 83.5))
        dxy = float(comm.get("dxy", 104.0))
        us_real_yield = float(comm.get("us_real_yield_10y", 2.0))
        central_bank_buying = bool(comm.get("central_bank_buying", False))
        geopolitical_risk = float(comm.get("geopolitical_risk_score", 0.5))

        # Gold fair value estimate: COMEX * USDINR / 31.1 (oz to gram) * 10
        gold_fair = (gold_comex * usd_inr / 31.1035) * 10
        gold_premium_pct = (gold_mcx - gold_fair) / gold_fair if gold_fair else 0

        score = 0.0
        risk = 0.4

        # DXY inverse relationship with gold
        if dxy < 100:
            score += 0.3
        elif dxy > 106:
            score -= 0.2

        # Real yields inverse with gold
        if us_real_yield < 0:
            score += 0.4
        elif us_real_yield < 1.0:
            score += 0.2
        elif us_real_yield > 2.5:
            score -= 0.2

        # Central bank buying = bullish
        if central_bank_buying:
            score += 0.25

        # Geopolitical risk = bullish for gold
        score += geopolitical_risk * 0.3

        # MCX premium/discount
        if gold_premium_pct > 0.03:
            score -= 0.1  # overpriced locally
        elif gold_premium_pct < -0.02:
            score += 0.1  # discount = buy opportunity

        confidence = min(0.9, 0.5 + abs(score) * 0.4)
        if score > 0.3:
            action = "buy"
        elif score < -0.2:
            action = "sell"
        else:
            action = "hold"

        rationale = (
            f"DXY={dxy}, real_yield={us_real_yield}%, "
            f"geo_risk={geopolitical_risk:.2f}, cb_buying={central_bank_buying}, "
            f"mcx_premium={gold_premium_pct:.1%}"
        )
        return self._output(action, confidence, self._clamp(risk),
                            ["GOLD", "SILVER", "GOLDM", "SILVERM"],
                            rationale,
                            {"gold_fair_value": round(gold_fair, 0), "gold_premium_pct": round(gold_premium_pct, 4)})
