from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis

from app.bus.event_bus import BUS
from app.bus.topics import MARKET_TICKS
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.state import STATE

logger = get_logger(__name__)

_TIMEFRAMES: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


@dataclass
class CandleBar:
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    ticks: int = 0

    def update(self, price: float, volume: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.ticks += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ts": self.ts.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "ticks": self.ticks,
        }


def _bar_start(ts: datetime, seconds: int) -> datetime:
    epoch = int(ts.timestamp())
    aligned = (epoch // seconds) * seconds
    return datetime.fromtimestamp(aligned, tz=UTC)


class TickAggregator:
    """
    Consumes ticks from "market_ticks" Redpanda topic (via Redis pub/sub fallback
    when Redpanda is unavailable), builds OHLC candles for 1m/5m/15m/1h,
    stores completed bars in Redis ZSET and updates STATE for mark-to-market.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._bars: dict[str, dict[str, CandleBar]] = defaultdict(dict)
        self._redis: redis.Redis | None = None
        self._pubsub: Any | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    def _update_state_mtm(self, symbol: str, price: float) -> None:
        pos = STATE.positions.get(symbol)
        if pos and pos.quantity != 0 and pos.avg_price > 0:
            pos.unrealized_pnl = (price - pos.avg_price) * pos.quantity

    async def _emit_closed_bar(self, bar: CandleBar) -> None:
        r = self._get_redis()
        key = f"candles:{bar.symbol}:{bar.timeframe}"
        score = bar.ts.timestamp()
        payload = json.dumps(bar.to_dict())
        try:
            await r.zadd(key, {payload: score})
            # keep last 500 candles per tf
            await r.zremrangebyrank(key, 0, -501)
            await r.expire(key, 86400 * 7)
            # pub/sub for live chart updates
            await r.publish(f"candles:{bar.timeframe}", payload)
        except Exception as exc:
            logger.warning("candle_emit_error", error=str(exc))

    async def _process_tick(self, symbol: str, price: float, volume: float, ts: datetime) -> None:
        self._update_state_mtm(symbol, price)

        for tf, seconds in _TIMEFRAMES.items():
            bar_start = _bar_start(ts, seconds)
            existing = self._bars[symbol].get(tf)

            if existing is None:
                self._bars[symbol][tf] = CandleBar(
                    symbol=symbol, timeframe=tf, ts=bar_start,
                    open=price, high=price, low=price, close=price, volume=volume, ticks=1,
                )
            elif existing.ts == bar_start:
                existing.update(price, volume)
            else:
                # bar closed — emit, start new
                await self._emit_closed_bar(existing)
                self._bars[symbol][tf] = CandleBar(
                    symbol=symbol, timeframe=tf, ts=bar_start,
                    open=price, high=price, low=price, close=price, volume=volume, ticks=1,
                )

    async def _consume_redis_pubsub(self) -> None:
        r = self._get_redis()
        self._pubsub = r.pubsub()
        await self._pubsub.subscribe("ticks:india", "ticks:crypto")
        logger.info("tick_aggregator_listening_redis_pubsub")

        async for message in self._pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                symbol = str(data["symbol"])
                price = float(data["price"])
                volume = float(data.get("volume", 0))
                ts_str = data.get("ts")
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(UTC)
                await self._process_tick(symbol, price, volume, ts)
            except Exception as exc:
                logger.warning("tick_aggregator_parse_error", error=str(exc))

    async def _consume_redpanda(self) -> None:
        logger.info("tick_aggregator_listening_redpanda")
        async for raw in BUS.subscribe(MARKET_TICKS, "tick-aggregator", "tick-aggregator-1"):
            try:
                symbol = str(raw.get("symbol", ""))
                price = float(raw.get("price", 0))
                volume = float(raw.get("volume", 0))
                ts_str = raw.get("ts")
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now(UTC)
                await self._process_tick(symbol, price, volume, ts)
            except Exception as exc:
                logger.warning("tick_aggregator_redpanda_error", error=str(exc))

    async def run(self) -> None:
        try:
            await self._consume_redpanda()
        except Exception as exc:
            logger.warning("tick_aggregator_redpanda_unavailable_falling_back", error=str(exc))
            await self._consume_redis_pubsub()

    async def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        r = self._get_redis()
        key = f"candles:{symbol}:{timeframe}"
        raw_items = await r.zrange(key, -limit, -1)
        return [json.loads(item) for item in raw_items]


TICK_AGGREGATOR = TickAggregator()
