"""Signal Fusion Engine — CORE

Consumes: features, news_signals (Redpanda)
          macro_data (latest cached in Redis)
Produces: unified_signal

Fusion formula:
  final_score = 0.4*market + 0.3*news + 0.2*macro + 0.1*social

Rules:
- Minimum confidence threshold (default 0.6)
- Reject stale signals (>300s old)
- Reject conflicting signals (|market - news| > 0.5 → HOLD)
- Persist unified_signals to Redis (latest per asset)
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

# ── Config ────────────────────────────────────────────────────────────────────
MIN_CONFIDENCE: float = float(getattr(settings, "min_signal_confidence", 0.6))
MAX_SIGNAL_AGE: int = int(getattr(settings, "max_signal_age_seconds", 300))
CONFLICT_THRESHOLD: float = float(getattr(settings, "signal_conflict_threshold", 0.5))

WEIGHTS = {"market": 0.4, "news": 0.3, "macro": 0.2, "social": 0.1}

# ── In-memory signal stores (per asset, latest value) ─────────────────────────
_market_signals: dict[str, dict[str, Any]] = {}   # asset → {score, ts}
_news_signals: dict[str, list[dict[str, Any]]] = defaultdict(list)  # asset → [signals]
_macro_signal: dict[str, Any] = {}                # single global macro state
_social_signals: dict[str, list[dict[str, Any]]] = defaultdict(list)


def _age_seconds(ts_str: str | None) -> float:
    if not ts_str:
        return MAX_SIGNAL_AGE + 1
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except ValueError:
        return MAX_SIGNAL_AGE + 1


def _market_score_from_features(feat: dict[str, Any]) -> float:
    """Derive a -1..1 market signal from feature record."""
    rsi = feat.get("rsi_14")
    mom = feat.get("momentum_10")
    ema9 = feat.get("ema_9")
    ema21 = feat.get("ema_21")
    ema50 = feat.get("ema_50")

    scores = []
    if rsi is not None:
        scores.append(max(-1.0, min(1.0, (float(rsi) - 50) / 50)))
    if mom is not None:
        scores.append(max(-1.0, min(1.0, float(mom) * 20)))
    if ema9 and ema21 and ema50:
        if ema9 > ema21 > ema50:
            scores.append(1.0)
        elif ema9 < ema21 < ema50:
            scores.append(-1.0)
        else:
            scores.append(0.0)

    return round(sum(scores) / max(len(scores), 1), 4) if scores else 0.0


def _macro_score() -> float:
    if not _macro_signal:
        return 0.0
    risk_on = _macro_signal.get("risk_on_score", 0.0) or 0.0
    usd_z = _macro_signal.get("usd_strength_zscore", 0.0) or 0.0
    # Strong USD is generally bearish for equities/gold
    return round(float(risk_on) - float(usd_z) * 0.1, 4)


def _news_score(asset: str) -> tuple[float, float]:
    """Returns (score, confidence) for asset from recent news signals."""
    signals = [s for s in _news_signals.get(asset, []) if _age_seconds(s.get("analyzed_at")) < MAX_SIGNAL_AGE]
    if not signals:
        return 0.0, 0.0
    weighted_sum = sum(s["sentiment"] * s["confidence"] for s in signals)
    total_conf = sum(s["confidence"] for s in signals)
    score = weighted_sum / max(total_conf, 1e-9)
    avg_conf = total_conf / len(signals)
    return round(score, 4), round(avg_conf, 4)


def _social_score(asset: str) -> float:
    signals = [s for s in _social_signals.get(asset, []) if _age_seconds(s.get("analyzed_at")) < MAX_SIGNAL_AGE]
    if not signals:
        return 0.0
    return round(sum(s["sentiment"] for s in signals) / len(signals), 4)


def _fuse(asset: str) -> dict[str, Any] | None:
    market_entry = _market_signals.get(asset)
    if market_entry and _age_seconds(market_entry.get("ts")) > MAX_SIGNAL_AGE:
        market_entry = None

    market = market_entry["score"] if market_entry else 0.0
    news, news_conf = _news_score(asset)
    macro = _macro_score()
    social = _social_score(asset)

    # Conflict check: market and news strongly disagree
    if abs(market - news) > CONFLICT_THRESHOLD and news_conf > 0.5:
        logger.info("signal_conflict_hold", asset=asset, market=market, news=news)
        return _emit(asset, 0.0, "HOLD", {"market": market, "news": news, "macro": macro, "social": social}, 0.5)

    final_score = (
        WEIGHTS["market"] * market
        + WEIGHTS["news"] * news
        + WEIGHTS["macro"] * macro
        + WEIGHTS["social"] * social
    )

    # Confidence: blend market recency + news confidence
    market_conf = 0.7 if market_entry else 0.3
    confidence = round(
        0.5 * market_conf
        + 0.4 * news_conf
        + 0.1 * (0.6 if _macro_signal else 0.3),
        4,
    )

    if confidence < MIN_CONFIDENCE:
        return None  # Not enough confidence — suppress signal

    return _emit(asset, final_score, _action(final_score), {
        "market": round(market, 4),
        "news": round(news, 4),
        "macro": round(macro, 4),
        "social": round(social, 4),
    }, confidence)


def _action(score: float) -> str:
    if score > 0.3:
        return "BUY"
    if score < -0.3:
        return "SELL"
    return "HOLD"


def _emit(asset: str, score: float, action: str, contributors: dict[str, float], confidence: float) -> dict[str, Any]:
    return {
        "asset": asset,
        "action": action,
        "final_score": round(score, 4),
        "confidence": confidence,
        "contributors": contributors,
        "weights_used": WEIGHTS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Consumers ─────────────────────────────────────────────────────────────────

async def _consume_features(redis: aioredis.Redis) -> None:
    async for record in consume("features", "fusion-features", "fusion-features-1"):
        try:
            rtype = record.get("type")
            if rtype == "market_feature":
                symbol = record.get("symbol", "")
                asset = symbol.split(":")[-1] if ":" in symbol else symbol
                score = _market_score_from_features(record)
                _market_signals[asset] = {"score": score, "ts": record.get("computed_at")}
                await _try_fuse(asset, redis)

            elif rtype == "macro_feature":
                _macro_signal.update(record)

        except Exception as exc:
            logger.error("fusion_features_error", error=str(exc))


async def _consume_news_signals(redis: aioredis.Redis) -> None:
    async for record in consume("news_signals", "fusion-news", "fusion-news-1"):
        try:
            asset = record.get("asset", "").upper()
            if not asset:
                continue
            source = record.get("source", "")
            is_social = any(s in source.lower() for s in ("reddit", "twitter", "telegram", "social"))
            if is_social:
                _social_signals[asset].append(record)
                if len(_social_signals[asset]) > 20:
                    _social_signals[asset] = _social_signals[asset][-20:]
            else:
                _news_signals[asset].append(record)
                if len(_news_signals[asset]) > 20:
                    _news_signals[asset] = _news_signals[asset][-20:]
            await _try_fuse(asset, redis)
        except Exception as exc:
            logger.error("fusion_news_error", error=str(exc))


async def _try_fuse(asset: str, redis: aioredis.Redis) -> None:
    signal = _fuse(asset)
    if signal is None:
        return
    await publish("unified_signal", signal)
    # Cache latest signal per asset in Redis (5 min TTL)
    await redis.setex(f"signal:{asset}", 300, json.dumps(signal))
    logger.info(
        "unified_signal_published",
        asset=asset,
        action=signal["action"],
        score=signal["final_score"],
        confidence=signal["confidence"],
    )


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("signal_fusion_engine_started", weights=WEIGHTS, min_confidence=MIN_CONFIDENCE)
    try:
        await asyncio.gather(
            _consume_features(redis),
            _consume_news_signals(redis),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
