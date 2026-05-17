from __future__ import annotations

import json
from typing import Any, Literal

import httpx
import redis.asyncio as aioredis
import structlog
from pydantic import BaseModel

from config import get_settings
from pipeline import Article

logger = structlog.get_logger(__name__)
settings = get_settings()

_SIGNAL_CHANNEL = "scrapling:signals"

_SYSTEM_PROMPT = """You are a financial intelligence analyst for Indian and global markets.
Given a news article, output a JSON object with these fields:
- sentiment: "bullish" | "bearish" | "neutral"
- impact: "high" | "medium" | "low"
- confidence: float 0-1
- affected_assets: list of ticker symbols or asset names (e.g. ["GOLD", "NIFTY", "BTC"])
- time_horizon: "intraday" | "swing" | "positional"
- rationale: one sentence explanation
Only output valid JSON, no markdown."""


class IntelligenceSignal(BaseModel):
    article_id: str
    source: str
    title: str
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    impact: Literal["high", "medium", "low"] = "low"
    confidence: float = 0.5
    affected_assets: list[str] = []
    time_horizon: Literal["intraday", "swing", "positional"] = "swing"
    rationale: str = ""
    published_at: str = ""


async def _call_llm(title: str, category: str) -> dict[str, Any]:
    if not settings.llm_api_url or not settings.llm_api_key:
        # Fallback: simple keyword heuristic
        lower = title.lower()
        sentiment = "bullish" if any(w in lower for w in ["surge", "rally", "gain", "rise", "up", "positive", "growth"]) \
            else "bearish" if any(w in lower for w in ["fall", "drop", "crash", "loss", "down", "negative", "cut"]) \
            else "neutral"
        return {"sentiment": sentiment, "impact": "medium", "confidence": 0.5,
                "affected_assets": [], "time_horizon": "swing", "rationale": "keyword heuristic"}

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Category: {category}\nHeadline: {title}"},
        ],
        "max_tokens": 200,
        "temperature": 0.1,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.llm_api_url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as exc:
        logger.warning("llm_call_error", error=str(exc))
        return {"sentiment": "neutral", "impact": "low", "confidence": 0.3,
                "affected_assets": [], "time_horizon": "swing", "rationale": "llm_unavailable"}


async def generate_signals(articles: list[Article]) -> list[IntelligenceSignal]:
    signals: list[IntelligenceSignal] = []
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    try:
        for article in articles:
            llm_out = await _call_llm(article.title, article.category)
            signal = IntelligenceSignal(
                article_id=article.id,
                source=article.source,
                title=article.title,
                sentiment=llm_out.get("sentiment", "neutral"),
                impact=llm_out.get("impact", "low"),
                confidence=float(llm_out.get("confidence", 0.5)),
                affected_assets=llm_out.get("affected_assets", []),
                time_horizon=llm_out.get("time_horizon", "swing"),
                rationale=llm_out.get("rationale", ""),
                published_at=article.published_at,
            )
            signals.append(signal)
            await redis.publish(_SIGNAL_CHANNEL, signal.model_dump_json())
    finally:
        await redis.aclose()

    return signals
