"""Normalization Service

Consumes: market_ticks, raw_news, macro_data
Produces: normalized_data

Responsibilities:
- Unify timestamps to UTC ISO-8601
- Normalize symbols (RELIANCE → NSE:RELIANCE)
- Deduplicate via Redis (5s TTL)
- Reject price spikes >10%
- Drop records with missing critical fields
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

# Symbol prefix map: bare symbol → exchange-prefixed
_EXCHANGE_MAP = {
    # India equities default to NSE
    "RELIANCE": "NSE:RELIANCE", "TCS": "NSE:TCS", "INFY": "NSE:INFY",
    "HDFCBANK": "NSE:HDFCBANK", "ICICIBANK": "NSE:ICICIBANK",
    "NIFTY": "NSE:NIFTY50", "BANKNIFTY": "NSE:BANKNIFTY",
    # Commodities
    "GOLD": "MCX:GOLD", "SILVER": "MCX:SILVER", "CRUDEOIL": "MCX:CRUDEOIL",
    # Crypto
    "BTC": "BINANCE:BTCUSDT", "ETH": "BINANCE:ETHUSDT",
    "BTCUSDT": "BINANCE:BTCUSDT", "ETHUSDT": "BINANCE:ETHUSDT",
}

_DEDUP_TTL = 5  # seconds


def _normalize_symbol(raw: str) -> str:
    raw = raw.upper().strip()
    if ":" in raw:
        return raw
    return _EXCHANGE_MAP.get(raw, f"NSE:{raw}")


def _to_utc(ts: Any) -> str:
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).isoformat()
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


async def _is_duplicate(redis: aioredis.Redis, key: str) -> bool:
    result = await redis.set(key, "1", nx=True, ex=_DEDUP_TTL)
    return result is None  # None means key already existed


def _normalize_tick(raw: dict[str, Any]) -> dict[str, Any] | None:
    price = raw.get("price")
    volume = raw.get("volume")
    symbol = raw.get("symbol", "")
    if price is None or volume is None or not symbol:
        return None
    try:
        price = float(price)
        volume = float(volume)
    except (TypeError, ValueError):
        return None
    return {
        "type": "tick",
        "symbol": _normalize_symbol(symbol),
        "price": price,
        "volume": volume,
        "source": raw.get("source", "market"),
        "exchange": raw.get("exchange", ""),
        "timestamp": _to_utc(raw.get("timestamp") or raw.get("ts")),
    }


def _normalize_news(raw: dict[str, Any]) -> dict[str, Any] | None:
    title = (raw.get("title") or "").strip()
    if len(title) < 10:
        return None
    return {
        "type": "news",
        "id": raw.get("id", ""),
        "title": title,
        "source": raw.get("source", ""),
        "url": raw.get("url", ""),
        "entities": raw.get("entities") or raw.get("affected_assets") or [],
        "category": raw.get("category", "general"),
        "sentiment": raw.get("sentiment"),
        "impact": raw.get("impact"),
        "confidence": raw.get("confidence"),
        "timestamp": _to_utc(raw.get("published_at") or raw.get("timestamp")),
    }


def _normalize_macro(raw: dict[str, Any]) -> dict[str, Any] | None:
    if not any(raw.get(k) is not None for k in ("dxy", "us10y", "vix", "sp500_change_pct")):
        return None
    return {
        "type": "macro",
        "dxy": raw.get("dxy"),
        "us10y": raw.get("us10y"),
        "vix": raw.get("vix"),
        "sp500_change_pct": raw.get("sp500_change_pct"),
        "nifty_change_pct": raw.get("nifty_change_pct"),
        "gold_usd": raw.get("gold_usd"),
        "timestamp": _to_utc(raw.get("timestamp")),
    }


# In-memory last-price cache for spike detection
_last_prices: dict[str, float] = {}


def _is_price_spike(symbol: str, price: float, threshold: float = 0.10) -> bool:
    last = _last_prices.get(symbol)
    if last is None:
        _last_prices[symbol] = price
        return False
    change = abs(price - last) / max(last, 1e-9)
    if change > threshold:
        logger.warning("price_spike_rejected", symbol=symbol, last=last, new=price, change_pct=round(change * 100, 2))
        return True
    _last_prices[symbol] = price
    return False


async def _process_topic(
    topic: str,
    group_id: str,
    consumer_id: str,
    normalizer: Any,
    redis: aioredis.Redis,
) -> None:
    async for raw in consume(topic, group_id, consumer_id):
        try:
            normalized = normalizer(raw)
            if normalized is None:
                continue

            # Spike filter for ticks
            if normalized["type"] == "tick" and _is_price_spike(normalized["symbol"], normalized["price"]):
                continue

            # Dedup key
            dedup_key = f"norm:dedup:{normalized['type']}:{normalized.get('symbol', normalized.get('id', ''))}"
            if await _is_duplicate(redis, dedup_key):
                continue

            normalized["normalized_at"] = datetime.now(timezone.utc).isoformat()
            await publish("normalized_data", normalized)
            logger.info("normalized", type=normalized["type"], symbol=normalized.get("symbol", normalized.get("id", "")))
        except Exception as exc:
            logger.error("normalization_error", topic=topic, error=str(exc))


async def run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("normalization_service_started")
    try:
        await asyncio.gather(
            _process_topic("market_ticks", "norm-market", "norm-market-1", _normalize_tick, redis),
            _process_topic("raw_news", "norm-news", "norm-news-1", _normalize_news, redis),
            _process_topic("macro_data", "norm-macro", "norm-macro-1", _normalize_macro, redis),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
