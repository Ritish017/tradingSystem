"""Hot-tier storage — Law 6.

Sub-millisecond access. Never persisted long.
Used for: live ticks, current positions, real-time quotes, signal cache.

All hot-tier reads/writes go through this module.
No other layer reaches Redis directly for state that belongs here.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.bus.topics import tick_key, signal_key, candles_key
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class HotStore:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: aioredis.Redis | None = None

    def _r(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    # ── Live ticks ────────────────────────────────────────────────────────────

    async def set_tick(self, symbol: str, price: float, ttl: int = 60) -> None:
        await self._r().set(tick_key(symbol), str(price), ex=ttl)

    async def get_tick(self, symbol: str) -> float | None:
        val = await self._r().get(tick_key(symbol))
        return float(val) if val is not None else None

    # ── Signal cache ──────────────────────────────────────────────────────────

    async def set_signal(self, asset: str, signal: dict[str, Any], ttl: int = 300) -> None:
        await self._r().setex(signal_key(asset), ttl, json.dumps(signal))

    async def get_signal(self, asset: str) -> dict[str, Any] | None:
        raw = await self._r().get(signal_key(asset))
        return json.loads(raw) if raw else None

    async def get_all_signals(self) -> dict[str, dict[str, Any]]:
        keys = await self._r().keys("signal:*")
        if not keys:
            return {}
        values = await self._r().mget(*keys)
        result = {}
        for key, val in zip(keys, values):
            if val:
                asset = key.split(":", 1)[1]
                try:
                    result[asset] = json.loads(val)
                except json.JSONDecodeError:
                    pass
        return result

    # ── Position mark-to-market ───────────────────────────────────────────────

    async def set_position_mtm(self, symbol: str, data: dict[str, Any]) -> None:
        await self._r().hset("positions:mtm", symbol, json.dumps(data))

    async def get_position_mtm(self, symbol: str) -> dict[str, Any] | None:
        raw = await self._r().hget("positions:mtm", symbol)
        return json.loads(raw) if raw else None

    # ── Candle ZSET (warm-tier boundary) ─────────────────────────────────────

    async def add_candle(self, symbol: str, timeframe: str, candle: dict, score: float) -> None:
        key = candles_key(symbol, timeframe)
        await self._r().zadd(key, {json.dumps(candle): score})
        await self._r().zremrangebyrank(key, 0, -501)  # keep last 500
        await self._r().expire(key, 86400 * 7)

    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> list[dict]:
        key = candles_key(symbol, timeframe)
        raw_items = await self._r().zrange(key, -limit, -1)
        return [json.loads(item) for item in raw_items]

    # ── Halt flag ─────────────────────────────────────────────────────────────

    async def set_halt(self, reason: str) -> None:
        await self._r().set("system:halt", reason)

    async def clear_halt(self) -> None:
        await self._r().delete("system:halt")

    async def get_halt(self) -> str | None:
        return await self._r().get("system:halt")


HOT = HotStore()
