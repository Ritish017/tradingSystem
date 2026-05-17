from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class QuantResearchAgent(BaseAgent):
    name = "quant_research"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        quant: dict[str, Any] = context.get("quant_data", {})

        zscore = float(quant.get("price_zscore_20d", 0.0))
        hurst_exp = float(quant.get("hurst_exponent", 0.5))
        realized_vol = float(quant.get("realized_vol_20d_ann", 0.2))
        implied_vol = float(quant.get("implied_vol", 0.22))
        skew = float(quant.get("vol_skew", 0.0))
        factor_momentum = float(quant.get("factor_momentum_score", 0.0))
        factor_value = float(quant.get("factor_value_score", 0.0))

        score = 0.0
        risk = 0.4

        # Mean reversion signal (Hurst < 0.5 = mean-reverting)
        if hurst_exp < 0.45:
            if zscore > 2.0:
                score -= 0.3  # sell the extreme
            elif zscore < -2.0:
                score += 0.3  # buy the dip
        elif hurst_exp > 0.55:
            # Trending: follow momentum
            score += factor_momentum * 0.3

        # Vol regime
        vol_ratio = implied_vol / realized_vol if realized_vol else 1.0
        if vol_ratio > 1.3:
            risk += 0.1  # vol premium elevated

        # Factor signals
        score += factor_value * 0.2
        score += factor_momentum * 0.2

        # Negative skew = tail risk
        if skew < -0.5:
            risk += 0.1

        confidence = min(0.85, 0.45 + abs(score) * 0.4)
        if score > 0.25:
            action = "buy"
        elif score < -0.2:
            action = "sell"
        else:
            action = "hold"

        rationale = (
            f"zscore={zscore:.2f}, hurst={hurst_exp:.2f}, "
            f"vol_ratio={vol_ratio:.2f}, momentum={factor_momentum:.2f}"
        )
        return self._output(action, confidence, self._clamp(risk), [], rationale,
                            {"zscore": zscore, "hurst": hurst_exp, "vol_ratio": round(vol_ratio, 3)})
