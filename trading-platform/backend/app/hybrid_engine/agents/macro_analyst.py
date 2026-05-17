"""Macro Analyst Agent

Consumes: features (type=macro_feature, via Redpanda)
Produces: news_signals (macro-typed signals for fusion engine)

Uses SUPER model (120B) via llm_router for macro regime analysis.
Runs every time a new macro_feature arrives.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.agents.llm_router import analyze_macro
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

# Only re-analyze if macro data changed meaningfully
_last_macro_hash: str = ""


def _macro_changed(snapshot: dict[str, Any]) -> bool:
    global _last_macro_hash
    key_fields = {k: round(float(snapshot[k]), 2) for k in ("dxy", "vix", "us10y") if snapshot.get(k) is not None}
    h = str(sorted(key_fields.items()))
    if h == _last_macro_hash:
        return False
    _last_macro_hash = h
    return True


def _build_macro_signal(router_out: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    result = router_out.get("result", {})
    regime = result.get("risk_regime", "neutral")
    equity_bias = float(result.get("equity_bias", 0.0))
    gold_bias = float(result.get("gold_bias", 0.0))
    confidence = float(router_out.get("confidence", 0.4))

    # Emit two signals: one for equities (NIFTY), one for gold
    return {
        "asset": "NIFTY50",
        "sentiment": round(max(-1.0, min(1.0, equity_bias)), 4),
        "impact": 60,
        "confidence": confidence,
        "time_horizon": "medium",
        "reasoning": result.get("key_driver", "macro_regime_analysis")[:200],
        "model_used": router_out.get("model_used", "120b"),
        "task_type": "macro_analysis",
        "escalated": router_out.get("escalated", False),
        "source": "macro_analyst",
        "source_id": f"macro_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        "macro_regime": regime,
        "gold_bias": round(max(-1.0, min(1.0, gold_bias)), 4),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("macro_analyst_agent_started")

    try:
        async for record in consume("features", "macro-analyst", "macro-analyst-1"):
            if record.get("type") != "macro_feature":
                continue
            try:
                snapshot = {
                    "dxy": record.get("dxy"),
                    "us10y": record.get("us10y"),
                    "vix": record.get("vix"),
                    "risk_on_score": record.get("risk_on_score"),
                    "usd_strength_zscore": record.get("usd_strength_zscore"),
                }
                if not _macro_changed(snapshot):
                    continue

                router_out = await analyze_macro(snapshot, redis)
                signal = _build_macro_signal(router_out, snapshot)
                await publish("news_signals", signal)

                # Also publish a gold signal from macro
                gold_signal = {**signal, "asset": "GOLD", "sentiment": signal["gold_bias"]}
                await publish("news_signals", gold_signal)

                logger.info(
                    "macro_signal_published",
                    regime=signal.get("macro_regime"),
                    equity_bias=signal["sentiment"],
                    gold_bias=signal["gold_bias"],
                    model=signal["model_used"],
                )
            except Exception as exc:
                logger.error("macro_analyst_error", error=str(exc))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
