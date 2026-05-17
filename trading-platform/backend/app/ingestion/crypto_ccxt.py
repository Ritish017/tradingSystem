from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Protocol, cast

import redis.asyncio as redis
import websockets

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import MarketTick
from app.ingestion.publisher import TickPublisher

logger = get_logger(__name__)


class RedisLike(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None) -> bool | None: ...


class WebSocketMessageSource(Protocol):
    async def recv(self) -> str: ...


WebSocketContextFactory = Callable[[str], AbstractAsyncContextManager[WebSocketMessageSource]]


def _default_websocket_connect(url: str) -> AbstractAsyncContextManager[WebSocketMessageSource]:
    return cast(AbstractAsyncContextManager[WebSocketMessageSource], websockets.connect(url))


class CryptoTickIngestionService:
    def __init__(
        self,
        *,
        redis_client: RedisLike | None = None,
        publisher: TickPublisher | None = None,
        websocket_connect: WebSocketContextFactory | None = None,
        binance_ws_url: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings
        if resolved_settings is None and (
            redis_client is None or publisher is None or binance_ws_url is None
        ):
            resolved_settings = get_settings()

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

        if binance_ws_url is None:
            if resolved_settings is None:
                raise RuntimeError("settings or binance_ws_url must be provided")
            self._binance_ws_url = resolved_settings.binance_ws_url
        else:
            self._binance_ws_url = binance_ws_url
        self._websocket_connect = websocket_connect or _default_websocket_connect

    @staticmethod
    def _normalise_symbol(symbol: str) -> str:
        return symbol.replace("/", "").upper()

    @staticmethod
    def parse_binance_message(payload: dict[str, object]) -> MarketTick:
        symbol = str(payload.get("s", "BTCUSDT"))
        price = float(payload.get("c", payload.get("p", 0.0)))
        volume = float(payload.get("v", payload.get("q", 0.0)))
        event_time = payload.get("E")
        if isinstance(event_time, int):
            ts = datetime.fromtimestamp(event_time / 1000, tz=UTC)
        else:
            ts = datetime.now(UTC)
        return MarketTick(symbol=symbol, source="binance", price=price, volume=volume, ts=ts)

    def build_stream_url(self, symbols: Iterable[str]) -> str:
        stream_names = "/".join(
            f"{self._normalise_symbol(symbol).lower()}@ticker"
            for symbol in symbols
        )
        base = self._binance_ws_url.rstrip("/")
        return f"{base}?streams={stream_names}"

    def parse_binance_payload(self, raw_message: str) -> MarketTick:
        payload = json.loads(raw_message)
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        if not isinstance(data, dict):
            raise ValueError("Invalid Binance payload")
        return self.parse_binance_message(cast(dict[str, object], data))

    async def handle_tick(self, tick: MarketTick) -> None:
        await self._publisher.publish_tick("ticks.crypto", tick)
        cache_key = f"tick:{self._normalise_symbol(tick.symbol)}"
        await self._redis.set(cache_key, f"{tick.price}", ex=60)

    async def stream_binance_tickers(
        self,
        symbols: Iterable[str],
        *,
        message_limit: int | None = None,
        reconnect_delay_seconds: float = 2.0,
    ) -> None:
        stream_url = self.build_stream_url(symbols)
        received = 0
        while True:
            try:
                async with self._websocket_connect(stream_url) as websocket:
                    while True:
                        raw_message = await websocket.recv()
                        tick = self.parse_binance_payload(raw_message)
                        await self.handle_tick(tick)
                        received += 1
                        if message_limit is not None and received >= message_limit:
                            return
            except Exception as exc:  # noqa: BLE001
                logger.warning("binance_stream_error", url=stream_url, error=str(exc))
                if message_limit is not None:
                    raise
                await asyncio.sleep(reconnect_delay_seconds)

