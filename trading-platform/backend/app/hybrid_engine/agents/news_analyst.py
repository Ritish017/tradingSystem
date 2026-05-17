"""LLM News Analyst Agent

Consumes: raw_news (Redis pub/sub: scrapling:signals)
          normalized_data (type=news, via Redpanda)
Produces: news_signals

Uses llm_router for intelligent model selection:
  - Short headlines / entity extraction → NANO (30B)
  - Full articles / high-impact events  → SUPER (120B)
  - Low-confidence NANO results         → escalated to SUPER

⚠️ HARD RULE: Never generates BUY/SELL. Output is classification/scoring only.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.agents.llm_router import (
    TaskType,
    analyze_high_impact_event,
    analyze_news,
    basic_sentiment,
    classify_task,
    extract_entities,
    route,
)
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

_HIGH_IMPACT_SOURCES = {"RBI", "SEBI", "FederalReserve", "IMF", "NSE", "BSE"}
_HIGH_IMPACT_KEYWORDS = {
    "rate cut", "rate hike", "gdp", "inflation", "earnings", "quarterly results",
    "merger", "acquisition", "ipo", "ban", "fraud", "default", "bankruptcy",
    "war", "sanctions", "geopolit",
}


def _is_high_impact(title: str, source: str, category: str) -> bool:
    lower = title.lower()
    return (
        source in _HIGH_IMPACT_SOURCES
        or category in ("monetary_policy", "regulatory", "corporate_filing")
        or any(kw in lower for kw in _HIGH_IMPACT_KEYWORDS)
    )


def _build_signal(raw: dict[str, Any], router_output: dict[str, Any]) -> dict[str, Any]:
    result = router_output.get("result", {})
    return {
        "asset": str(result.get("asset") or result.get("tickers", ["NIFTY"])[0] if isinstance(result.get("tickers"), list) else "NIFTY").upper(),
        "sentiment": float(max(-1.0, min(1.0, result.get("sentiment", 0.0)))),
        "impact": int(max(0, min(100, result.get("impact", 30)))),
        "confidence": float(max(0.0, min(1.0, router_output.get("confidence", 0.4)))),
        "time_horizon": result.get("time_horizon", "short"),
        "reasoning": str(result.get("reasoning") or result.get("key_driver", ""))[:200],
        "model_used": router_output.get("model_used", "fallback"),
        "task_type": router_output.get("task_type", ""),
        "escalated": router_output.get("escalated", False),
        "source_id": raw.get("id", ""),
        "source": raw.get("source", ""),
        "title": raw.get("title", "")[:200],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _analyze_article(
    title: str,
    body: str,
    entities: list[str],
    source: str,
    category: str,
    redis: aioredis.Redis,
) -> dict[str, Any]:
    """Route article to correct model based on content and source."""

    # Step 1: Entity extraction always via NANO (fast, cheap)
    if not entities:
        entity_result = await extract_entities(title, redis)
        extracted = entity_result.get("result", {})
        entities = (
            extracted.get("tickers", [])
            + extracted.get("commodities", [])
            + extracted.get("indices", [])
        )

    # Step 2: Route main analysis
    if _is_high_impact(title, source, category):
        return await analyze_high_impact_event(f"{title}\n{body[:500]}", redis)

    if body and len(body) > 200:
        return await analyze_news(title, body, entities, redis)

    # Short headline — try NANO first, router will escalate if needed
    return await route(title, None, redis, f"Entities: {', '.join(entities[:5])}" if entities else "")


async def _process_redis_channel(redis: aioredis.Redis) -> None:
    """Low-latency path: consume scrapling pub/sub signals."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("scrapling:signals")
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            raw = json.loads(message["data"])
            title = raw.get("title", "")
            entities = raw.get("affected_assets", [])
            source = raw.get("source", "")
            category = raw.get("category", "general")

            router_out = await _analyze_article(title, "", entities, source, category, redis)
            signal = _build_signal(raw, router_out)
            await publish("news_signals", signal)
            logger.info(
                "news_signal_published",
                asset=signal["asset"],
                sentiment=signal["sentiment"],
                model=signal["model_used"],
                escalated=signal["escalated"],
            )
        except Exception as exc:
            logger.error("redis_channel_error", error=str(exc))


async def _process_normalized_news(redis: aioredis.Redis) -> None:
    """Redpanda path: consume normalized news records."""
    async for record in consume("normalized_data", "llm-agent", "llm-agent-1"):
        if record.get("type") != "news":
            continue
        try:
            title = record.get("title", "")
            body = record.get("body", "")
            entities = record.get("entities", [])
            source = record.get("source", "")
            category = record.get("category", "general")

            router_out = await _analyze_article(title, body, entities, source, category, redis)
            signal = _build_signal(record, router_out)
            await publish("news_signals", signal)
            logger.info(
                "news_signal_published",
                asset=signal["asset"],
                confidence=signal["confidence"],
                model=signal["model_used"],
                latency_ms=router_out.get("latency_ms", 0),
            )
        except Exception as exc:
            logger.error("normalized_news_error", error=str(exc))


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info(
        "llm_agent_service_started",
        super_model=getattr(settings, "nvidia_super_model", ""),
        nano_model=getattr(settings, "nvidia_nano_model", ""),
    )
    try:
        await asyncio.gather(
            _process_redis_channel(redis),
            _process_normalized_news(redis),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
