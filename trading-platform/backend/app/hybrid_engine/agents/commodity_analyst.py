"""Commodity Analyst Agent

Consumes: features (macro_feature) + news_signals (GOLD/SILVER)
Produces: news_signals (commodity-typed signals)

Uses SUPER model (120B) via llm_router — commodity analysis always
requires deep reasoning about USD, inflation, geopolitics, India premium.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.agents.llm_router import analyze_commodity
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

_POLL_INTERVAL = 90  # seconds between commodity analysis cycles
_macro_state: dict[str, Any] = {}
_commodity_news: dict[str, list[str]] = {"GOLD": [], "SILVER": [], "CRUDEOIL": []}


def _build_context(asset: str, macro: dict[str, Any], recent_headlines: list[str]) -> str:
    lines = [f"Asset: {asset}"]
    if macro.get("dxy"):
        lines.append(f"USD Index (DXY): {macro['dxy']}")
    if macro.get("us10y"):
        lines.append(f"US 10Y Yield: {macro['us10y']}%")
    if macro.get("vix"):
        lines.append(f"VIX: {macro['vix']}")
    if macro.get("gold_usd"):
        lines.append(f"Gold spot (USD): {macro['gold_usd']}")
    if recent_headlines:
        lines.append("Recent headlines:")
        for h in recent_headlines[-5:]:
            lines.append(f"  - {h}")
    return "\n".join(lines)


def _build_signal(asset: str, router_out: dict[str, Any]) -> dict[str, Any]:
    result = router_out.get("result", {})
    sentiment = float(result.get("sentiment", 0.0))
    confidence = float(router_out.get("confidence", 0.4))
    bias = result.get("bias", "neutral")
    return {
        "asset": asset,
        "sentiment": round(max(-1.0, min(1.0, sentiment)), 4),
        "impact": 65,
        "confidence": confidence,
        "time_horizon": "medium",
        "reasoning": str(result.get("key_driver", "commodity_analysis"))[:200],
        "model_used": router_out.get("model_used", "120b"),
        "task_type": "commodity_intelligence",
        "escalated": router_out.get("escalated", False),
        "source": "commodity_analyst",
        "source_id": f"commodity_{asset}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        "bias": bias,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _consume_macro() -> None:
    async for record in consume("features", "commodity-analyst-macro", "commodity-analyst-macro-1"):
        if record.get("type") == "macro_feature":
            _macro_state.update(record)


async def _consume_news() -> None:
    async for record in consume("news_signals", "commodity-analyst-news", "commodity-analyst-news-1"):
        asset = record.get("asset", "").upper()
        if asset in _commodity_news:
            title = record.get("title", "")
            if title:
                _commodity_news[asset].append(title)
                if len(_commodity_news[asset]) > 20:
                    _commodity_news[asset] = _commodity_news[asset][-20:]


async def _analysis_loop(redis: aioredis.Redis) -> None:
    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        if not _macro_state:
            continue
        for asset in ("GOLD", "SILVER"):
            try:
                context = _build_context(asset, _macro_state, _commodity_news.get(asset, []))
                router_out = await analyze_commodity(context, redis)
                signal = _build_signal(asset, router_out)
                await publish("news_signals", signal)
                logger.info(
                    "commodity_signal_published",
                    asset=asset,
                    bias=signal["bias"],
                    confidence=signal["confidence"],
                    model=signal["model_used"],
                )
            except Exception as exc:
                logger.error("commodity_analyst_error", asset=asset, error=str(exc))


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("commodity_analyst_agent_started")
    try:
        await asyncio.gather(
            _consume_macro(),
            _consume_news(),
            _analysis_loop(redis),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
