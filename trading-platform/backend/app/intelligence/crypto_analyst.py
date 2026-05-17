from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class CryptoAnalystAgent(BaseAgent):
    name = "crypto_analyst"

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        crypto: dict[str, Any] = context.get("crypto_data", {})

        btc_price = float(crypto.get("btc_price", 65000))
        btc_funding_rate = float(crypto.get("btc_funding_rate", 0.01))  # 8h %
        btc_oi_change_pct = float(crypto.get("btc_oi_change_24h_pct", 0.0))
        fear_greed = float(crypto.get("fear_greed_index", 50))  # 0-100
        btc_dominance = float(crypto.get("btc_dominance_pct", 52.0))
        liquidations_24h_usd = float(crypto.get("liquidations_24h_usd", 100_000_000))
        nasdaq_corr = float(crypto.get("btc_nasdaq_30d_corr", 0.6))

        score = 0.0
        risk = 0.5

        # Fear & Greed: extreme fear = contrarian buy
        if fear_greed < 20:
            score += 0.4
            risk -= 0.1
        elif fear_greed > 80:
            score -= 0.3
            risk += 0.1

        # Funding rate: very positive = crowded longs = bearish
        if btc_funding_rate > 0.05:
            score -= 0.3
            risk += 0.15
        elif btc_funding_rate < -0.01:
            score += 0.2  # shorts crowded = squeeze potential

        # OI increasing with price = bullish confirmation
        if btc_oi_change_pct > 5:
            score += 0.15
        elif btc_oi_change_pct < -10:
            score -= 0.2
            risk += 0.1

        # Large liquidations = volatility spike
        if liquidations_24h_usd > 500_000_000:
            risk += 0.2

        confidence = min(0.85, 0.45 + abs(score) * 0.4)
        if score > 0.25:
            action = "buy"
        elif score < -0.2:
            action = "sell"
        else:
            action = "hold"

        rationale = (
            f"F&G={fear_greed:.0f}, funding={btc_funding_rate:.3f}%, "
            f"OI_chg={btc_oi_change_pct:.1f}%, liq={liquidations_24h_usd/1e6:.0f}M"
        )
        return self._output(action, confidence, self._clamp(risk),
                            ["BTC", "ETH", "BTCUSDT"],
                            rationale,
                            {"fear_greed": fear_greed, "funding_rate": btc_funding_rate})
