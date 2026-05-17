from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx
import redis.asyncio as redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"

Interval = Literal[
    "ONE_MINUTE", "THREE_MINUTE", "FIVE_MINUTE", "TEN_MINUTE",
    "FIFTEEN_MINUTE", "THIRTY_MINUTE", "ONE_HOUR", "ONE_DAY",
]

_INTERVAL_SECONDS = {
    "ONE_MINUTE": 60,
    "THREE_MINUTE": 180,
    "FIVE_MINUTE": 300,
    "TEN_MINUTE": 600,
    "FIFTEEN_MINUTE": 900,
    "THIRTY_MINUTE": 1800,
    "ONE_HOUR": 3600,
    "ONE_DAY": 86400,
}


def _ts_to_dt(ts_str: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.now(UTC)


class HistoricalService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def _fetch_candles(
        self,
        exchange: str,
        symboltoken: str,
        interval: Interval,
        fromdate: str,
        todate: str,
    ) -> list[list[Any]]:
        headers = await ANGEL_SESSION.get_headers()
        payload = {
            "exchange": exchange,
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": fromdate,
            "todate": todate,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_BASE}/rest/secure/angelbroking/historical/v3/getCandleData",
                json=payload,
                headers=headers,
            )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"historical fetch failed: {body.get('message')}")
        return body.get("data", []) or []

    async def get_candles(
        self,
        exchange: str,
        symboltoken: str,
        interval: Interval,
        from_dt: datetime,
        to_dt: datetime,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        cache_key = f"candles:{exchange}:{symboltoken}:{interval}:{from_dt.date()}:{to_dt.date()}"
        r = self._get_redis()

        if use_cache:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)

        fromdate = from_dt.strftime("%Y-%m-%d %H:%M")
        todate = to_dt.strftime("%Y-%m-%d %H:%M")
        raw = await self._fetch_candles(exchange, symboltoken, interval, fromdate, todate)

        candles = []
        for row in raw:
            if len(row) < 6:
                continue
            candles.append(
                {
                    "ts": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": int(row[5]),
                }
            )

        ttl = 60 if interval == "ONE_MINUTE" else 300
        await r.set(cache_key, json.dumps(candles), ex=ttl)
        logger.info(
            "historical_candles_fetched",
            symbol=symboltoken,
            interval=interval,
            count=len(candles),
        )
        return candles

    async def backfill(
        self,
        exchange: str,
        symboltoken: str,
        interval: Interval,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Fetch up to `days` of history, chunking into 60-day windows."""
        to_dt = datetime.now(UTC)
        from_dt = to_dt - timedelta(days=days)
        all_candles: list[dict[str, Any]] = []
        chunk_days = 59
        cursor = from_dt
        while cursor < to_dt:
            chunk_end = min(cursor + timedelta(days=chunk_days), to_dt)
            chunk = await self.get_candles(
                exchange, symboltoken, interval, cursor, chunk_end, use_cache=False
            )
            all_candles.extend(chunk)
            cursor = chunk_end
        return all_candles


HISTORICAL = HistoricalService()
