from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

import redis.asyncio as redis

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import MarketTick
from app.ingestion.publisher import TickPublisher

logger = get_logger(__name__)


class RedisLike(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None) -> bool | None: ...


class KiteTickIngestionService:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        redis_client: RedisLike | None = None,
        publisher: TickPublisher | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings
        if resolved_settings is None and (
            enabled is None or redis_client is None or publisher is None
        ):
            resolved_settings = get_settings()

        if enabled is None:
            self.enabled = (
                resolved_settings.kite_ws_enabled
                if resolved_settings is not None
                else False
            )
        else:
            self.enabled = enabled

        if redis_client is None:
            if resolved_settings is None:
                raise RuntimeError("settings or redis_client must be provided")
            self._redis = redis.from_url(resolved_settings.redis_url, decode_responses=True)
        else:
            self._redis = redis_client

        if publisher is None:
            self._publisher = TickPublisher(settings=resolved_settings)
        else:
            self._publisher = publisher

    async def handle_kite_tick(
        self,
        instrument: str,
        last_price: float,
        volume: float,
        *,
        ts: datetime | None = None,
    ) -> MarketTick:
        if not self.enabled:
            raise RuntimeError("Kite ingestion is feature-flagged off")
        tick = MarketTick(
            symbol=instrument,
            source="kite_ws",
            price=last_price,
            volume=volume,
            ts=ts or datetime.now(UTC),
        )
        await self._publisher.publish_tick("ticks.india.live", tick)
        await self._redis.set(f"tick:{instrument.upper()}", f"{tick.price}", ex=60)
        return tick

    async def handle_kite_tick_payload(self, payload: dict[str, object]) -> MarketTick:
        symbol = str(
            payload.get("tradingsymbol")
            or payload.get("symbol")
            or payload.get("instrument_token")
            or ""
        )
        if not symbol:
            raise ValueError("Missing tradingsymbol/symbol in Kite tick payload")
        last_price = float(payload.get("last_price", payload.get("lp", payload.get("ltp", 0.0))))
        volume = float(payload.get("volume", payload.get("last_quantity", 0.0)))
        ts = self._parse_timestamp(payload.get("timestamp"))
        return await self.handle_kite_tick(symbol, last_price, volume, ts=ts)

    async def process_tick_batch(self, ticks: Sequence[dict[str, object]]) -> list[MarketTick]:
        results: list[MarketTick] = []
        for tick in ticks:
            results.append(await self.handle_kite_tick_payload(tick))
        return results

    async def stream_with_kiteticker(
        self,
        *,
        api_key: str,
        access_token: str,
        instrument_tokens: Sequence[int],
    ) -> None:
        if not self.enabled:
            raise RuntimeError("Kite ingestion is feature-flagged off")
        from kiteconnect import KiteTicker

        ticker = KiteTicker(api_key, access_token)
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_connect(ws: Any, response: object) -> None:
            del response
            ws.subscribe(list(instrument_tokens))
            ws.set_mode(ws.MODE_FULL, list(instrument_tokens))

        def on_ticks(ws: object, ticks: list[dict[str, object]]) -> None:
            del ws
            for tick in ticks:
                loop.call_soon_threadsafe(queue.put_nowait, tick)

        def on_error(ws: object, code: int, reason: str) -> None:
            del ws
            logger.error("kite_ws_error", code=code, reason=reason)

        ticker.on_connect = on_connect
        ticker.on_ticks = on_ticks
        ticker.on_error = on_error
        ticker.connect(threaded=True)
        try:
            while True:
                tick = await queue.get()
                await self.handle_kite_tick_payload(tick)
        finally:
            ticker.stop()

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(UTC)
        if isinstance(value, int):
            if value > 10_000_000_000:
                return datetime.fromtimestamp(value / 1000, tz=UTC)
            return datetime.fromtimestamp(value, tz=UTC)
        if isinstance(value, str):
            cleaned = value.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(cleaned)
                return parsed.astimezone(UTC)
            except ValueError:
                return datetime.now(UTC)
        return datetime.now(UTC)

