"""Commodity Intelligence Engine

Tracks Gold & Silver with multi-factor bias scoring:
- USD strength (DXY) — inverse correlation
- Inflation (CPI / real yields)
- Geopolitical risk (news keyword scan)
- India premium (MCX vs COMEX spread)

Publishes to: unified_signal (commodity assets)
Also updates Redis cache for API reads.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.bus.event_bus import BUS
from app.bus.topics import FEATURES, NEWS_SIGNALS, UNIFIED_SIGNAL
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_POLL_INTERVAL = 60
_GEO_KEYWORDS = {"war", "sanctions", "conflict", "attack", "crisis", "tension", "nuclear", "invasion"}

# Latest macro state (updated from features topic)
_macro: dict[str, Any] = {}
# Latest news signals for GOLD/SILVER
_commodity_news: dict[str, list[dict[str, Any]]] = {"GOLD": [], "SILVER": []}


def _dxy_signal(dxy: float | None) -> float:
    """Strong USD → bearish gold. Returns -1..1."""
    if dxy is None:
        return 0.0
    # DXY ~100 is neutral; >106 bearish, <95 bullish
    return round(max(-1.0, min(1.0, (100 - dxy) / 10)), 4)


def _inflation_signal(us10y: float | None, vix: float | None) -> float:
    """Low real yields + high VIX → bullish gold."""
    score = 0.0
    if us10y is not None:
        # Yield < 2% → bullish, > 5% → bearish
        score += max(-1.0, min(1.0, (2.5 - float(us10y)) / 2.5))
    if vix is not None:
        # High VIX → safe haven demand
        score += max(0.0, min(0.5, (float(vix) - 15) / 30))
    return round(score / 2, 4)


def _geopolitical_signal(news_signals: list[dict[str, Any]]) -> float:
    """Scan recent news for geopolitical keywords → bullish gold."""
    if not news_signals:
        return 0.0
    geo_count = sum(
        1 for s in news_signals
        if any(kw in s.get("title", "").lower() for kw in _GEO_KEYWORDS)
    )
    return round(min(1.0, geo_count / max(len(news_signals), 1) * 3), 4)


def _india_premium_signal(gold_mcx_inr: float | None, gold_usd: float | None, usd_inr: float = 83.5) -> float:
    """Positive India premium → local demand → mildly bullish."""
    if gold_mcx_inr is None or gold_usd is None:
        return 0.0
    # Convert COMEX to INR per 10g (1 troy oz = 31.1g)
    comex_inr_per10g = gold_usd * usd_inr / 31.1 * 10
    premium_pct = (gold_mcx_inr - comex_inr_per10g) / max(comex_inr_per10g, 1) * 100
    return round(max(-0.5, min(0.5, premium_pct / 5)), 4)


def _compute_bias(asset: str, macro: dict[str, Any], news: list[dict[str, Any]]) -> dict[str, Any]:
    dxy = macro.get("dxy")
    us10y = macro.get("us10y")
    vix = macro.get("vix")
    gold_usd = macro.get("gold_usd")

    dxy_s = _dxy_signal(dxy)
    inf_s = _inflation_signal(us10y, vix)
    geo_s = _geopolitical_signal(news)
    india_s = _india_premium_signal(None, gold_usd)  # MCX price not yet wired

    # News sentiment for this asset
    news_s = 0.0
    if news:
        news_s = sum(n.get("sentiment", 0.0) for n in news[-5:]) / min(len(news), 5)

    score = (
        0.35 * dxy_s
        + 0.25 * inf_s
        + 0.20 * geo_s
        + 0.10 * india_s
        + 0.10 * news_s
    )
    score = round(score, 4)
    confidence = round(
        0.5 + abs(score) * 0.4 + (0.1 if len(news) > 2 else 0.0),
        4,
    )
    confidence = min(0.95, confidence)

    bias = "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral"

    return {
        "asset": asset,
        "action": "BUY" if score > 0.2 else "SELL" if score < -0.2 else "HOLD",
        "final_score": score,
        "confidence": confidence,
        "bias": bias,
        "contributors": {
            "usd_strength": round(dxy_s, 4),
            "inflation_yields": round(inf_s, 4),
            "geopolitical": round(geo_s, 4),
            "india_premium": round(india_s, 4),
            "news_sentiment": round(news_s, 4),
        },
        "macro_snapshot": {
            "dxy": dxy,
            "us10y": us10y,
            "vix": vix,
            "gold_usd": gold_usd,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _consume_macro_features() -> None:
    async for record in BUS.subscribe(FEATURES, "commodity-macro", "commodity-macro-1"):
        if record.get("type") == "macro_feature":
            _macro.update(record)


async def _consume_news_signals() -> None:
    async for record in BUS.subscribe(NEWS_SIGNALS, "commodity-news", "commodity-news-1"):
        asset = record.get("asset", "").upper()
        if asset in _commodity_news:
            _commodity_news[asset].append(record)
            if len(_commodity_news[asset]) > 30:
                _commodity_news[asset] = _commodity_news[asset][-30:]


async def _publish_loop(redis: aioredis.Redis) -> None:
    while True:
        await asyncio.sleep(_POLL_INTERVAL)
        if not _macro:
            continue
        for asset in ("GOLD", "SILVER"):
            try:
                signal = _compute_bias(asset, _macro, _commodity_news.get(asset, []))
                await BUS.publish(UNIFIED_SIGNAL, signal)
                await redis.setex(f"signal:{asset}", 300, json.dumps(signal))
                logger.info("commodity_signal", asset=asset, bias=signal["bias"], confidence=signal["confidence"])
            except Exception as exc:
                logger.error("commodity_signal_error", asset=asset, error=str(exc))


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("commodity_intelligence_engine_started")
    try:
        await asyncio.gather(
            _consume_macro_features(),
            _consume_news_signals(),
            _publish_loop(redis),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
