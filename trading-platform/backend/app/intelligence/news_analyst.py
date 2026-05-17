from __future__ import annotations

from typing import Any

from app.intelligence.base_agent import AgentOutput, BaseAgent


class NewsAnalystAgent(BaseAgent):
    name = "news_analyst"

    _BULLISH_WORDS = {"surge", "rally", "gain", "rise", "positive", "growth", "beat", "upgrade", "buy"}
    _BEARISH_WORDS = {"fall", "drop", "crash", "loss", "negative", "miss", "downgrade", "sell", "cut", "ban"}

    async def analyze(self, context: dict[str, Any]) -> AgentOutput:
        signals: list[dict[str, Any]] = context.get("intelligence_signals", [])
        if not signals:
            return self._output("hold", 0.3, 0.3, [], "no_signals")

        bullish = sum(1 for s in signals if s.get("sentiment") == "bullish")
        bearish = sum(1 for s in signals if s.get("sentiment") == "bearish")
        high_impact = [s for s in signals if s.get("impact") == "high"]

        total = len(signals)
        bull_ratio = bullish / total if total else 0.5
        bear_ratio = bearish / total if total else 0.5

        avg_confidence = sum(s.get("confidence", 0.5) for s in signals) / total if total else 0.5
        impact_boost = 0.15 if high_impact else 0.0

        assets: list[str] = []
        for s in signals:
            assets.extend(s.get("affected_assets", []))
        assets = list(set(assets))[:10]

        if bull_ratio > 0.6:
            action, confidence, risk = "buy", avg_confidence + impact_boost, 0.35
            rationale = f"{bullish}/{total} bullish signals, {len(high_impact)} high-impact"
        elif bear_ratio > 0.6:
            action, confidence, risk = "sell", avg_confidence + impact_boost, 0.65
            rationale = f"{bearish}/{total} bearish signals, {len(high_impact)} high-impact"
        else:
            action, confidence, risk = "hold", avg_confidence, 0.5
            rationale = f"mixed signals: {bullish} bull / {bearish} bear"

        return self._output(action, confidence, risk, assets, rationale,
                            {"total_signals": total, "high_impact_count": len(high_impact)})
