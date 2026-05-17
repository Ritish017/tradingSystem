from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class TechnicalAnalystAgent(BaseAgent):
    name = "technical_analyst"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        tech: dict[str, Any] = context.get("technical_data", {})
        symbol = tech.get("symbol", "NIFTY")

        rsi = float(tech.get("rsi_14", 50.0))
        macd_hist = float(tech.get("macd_histogram", 0.0))
        price = float(tech.get("price", 0.0))
        sma_20 = float(tech.get("sma_20", price))
        sma_50 = float(tech.get("sma_50", price))
        atr = float(tech.get("atr_14", 1.0))
        volume_ratio = float(tech.get("volume_ratio", 1.0))  # current/avg

        score = 0.0
        risk = 0.4

        # RSI signals
        if rsi < 30:
            score += 0.4  # oversold
        elif rsi > 70:
            score -= 0.4  # overbought
        elif rsi < 45:
            score += 0.1
        elif rsi > 55:
            score -= 0.1

        # MACD
        if macd_hist > 0:
            score += 0.2
        else:
            score -= 0.2

        # Price vs MAs
        if price > sma_20 > sma_50:
            score += 0.2  # uptrend
        elif price < sma_20 < sma_50:
            score -= 0.2  # downtrend

        # Volume confirmation
        if volume_ratio > 1.5 and score > 0:
            score += 0.1
            risk -= 0.05
        elif volume_ratio > 1.5 and score < 0:
            score -= 0.1
            risk += 0.05

        # High ATR = higher risk
        if atr / price > 0.02:
            risk += 0.1

        confidence = min(0.9, 0.4 + abs(score) * 0.5)
        if score > 0.3:
            action = "buy"
        elif score < -0.3:
            action = "sell"
        else:
            action = "hold"

        rationale = f"RSI={rsi:.1f}, MACD_hist={macd_hist:.2f}, price_vs_sma20={'above' if price > sma_20 else 'below'}"
        return self._output(action, confidence, self._clamp(risk), [symbol], rationale,
                            {"rsi": rsi, "macd_histogram": macd_hist, "volume_ratio": volume_ratio})
