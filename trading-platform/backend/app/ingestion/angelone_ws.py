from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.types import MarketTick
from app.ingestion.publisher import TickPublisher
from app.services.angelone.websocket import ANGEL_WS

logger = get_logger(__name__)

_DEFAULT_NSE_TOKENS = [
    "3045",   # SBIN
    "1594",   # INFY
    "2885",   # RELIANCE
    "11536",  # TCS
    "5633",   # BAJFINANCE
    "99926004",  # NIFTY 50 Index
    "99926009",  # BANK NIFTY Index
]

_DEFAULT_NFO_TOKENS: list[str] = []  # Populated dynamically from subscriptions


def _parse_angel_tick(raw: dict[str, Any]) -> MarketTick | None:
    try:
        token = str(raw.get("token", raw.get("symbolToken", "")))
        symbol = str(raw.get("trading_symbol", raw.get("tradingSymbol", token)))
        ltp_raw = raw.get("last_traded_price", raw.get("ltp", 0))
        price = float(ltp_raw) / 100.0 if isinstance(ltp_raw, int) and ltp_raw > 10000 else float(ltp_raw or 0)
        volume = float(raw.get("volume_trade_for_the_day", raw.get("volume", 0)) or 0)
        ts_raw = raw.get("exchange_timestamp", raw.get("timestamp"))
        if isinstance(ts_raw, int):
            ts = datetime.fromtimestamp(ts_raw / 1000, tz=UTC)
        else:
            ts = datetime.now(UTC)
        return MarketTick(symbol=symbol, source="angelone", price=price, volume=volume, ts=ts)
    except Exception as exc:
        logger.warning("angelone_tick_parse_error", error=str(exc), raw=str(raw)[:200])
        return None


class AngelOneTickIngestionService:
    """
    Subscribes to Angel One WebSocket ticks and publishes them to:
    - Redpanda topic "market_ticks" (alongside Binance)
    - Redis pub/sub channel "ticks:india"
    - Redis cache key "tick:{symbol}"
    """

    def __init__(
        self,
        nse_tokens: list[str] | None = None,
        nfo_tokens: list[str] | None = None,
    ) -> None:
        self._settings = get_settings()
        self._nse_tokens = nse_tokens or _DEFAULT_NSE_TOKENS
        self._nfo_tokens = nfo_tokens or _DEFAULT_NFO_TOKENS
        self._publisher: TickPublisher | None = None
        self._redis: redis.Redis | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    def _get_publisher(self) -> TickPublisher:
        if self._publisher is None:
            self._publisher = TickPublisher(settings=self._settings)
        return self._publisher

    async def _handle_tick(self, raw: dict[str, Any]) -> None:
        tick = _parse_angel_tick(raw)
        if tick is None:
            return
        r = self._get_redis()
        # publish to Redpanda + InfluxDB via shared publisher
        try:
            await self._get_publisher().publish_tick("market_ticks", tick)
        except Exception as exc:
            logger.warning("angelone_publish_error", error=str(exc))

        # Redis cache
        try:
            await r.set(f"tick:{tick.symbol}", tick.price, ex=60)
            # pub/sub for WebSocket relay
            await r.publish("ticks:india", json.dumps({"symbol": tick.symbol, "price": tick.price, "ts": tick.ts.isoformat()}))
        except Exception as exc:
            logger.warning("angelone_redis_error", error=str(exc))

    async def run(self) -> None:
        # Register subscriptions
        if self._nse_tokens:
            ANGEL_WS.add_subscription("NSE", self._nse_tokens, mode=2, correlation_id="nse-ticks")
        if self._nfo_tokens:
            ANGEL_WS.add_subscription("NFO", self._nfo_tokens, mode=2, correlation_id="nfo-ticks")

        await ANGEL_WS.start()
        logger.info(
            "angelone_ingestion_started",
            nse_tokens=len(self._nse_tokens),
            nfo_tokens=len(self._nfo_tokens),
        )

        async for tick in ANGEL_WS.stream():
            await self._handle_tick(tick)

    def subscribe_tokens(self, exchange: str, tokens: list[str]) -> None:
        ANGEL_WS.subscribe(exchange, tokens, mode=2)


ANGEL_INGESTION = AngelOneTickIngestionService()
