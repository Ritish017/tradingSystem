from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"

_MODE_LTP = "LTP"
_MODE_FULL = "FULL"
_MODE_OHLC = "OHLC"


def _paise_to_rupees(val: Any) -> float:
    try:
        return float(val) / 100.0
    except (TypeError, ValueError):
        return 0.0


class MarketDataService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _get_quote(
        self,
        mode: str,
        exchange: str,
        symbol: str,
        token: str,
    ) -> dict[str, Any]:
        import httpx

        headers = await ANGEL_SESSION.get_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_BASE}/rest/secure/angelbroking/market/v1/quote/",
                json={"mode": mode, "exchangeTokens": {exchange: [token]}},
                headers=headers,
            )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"quote failed: {body.get('message')}")
        fetched = body.get("data", {}).get("fetched", [])
        return fetched[0] if fetched else {}

    async def get_ltp(self, exchange: str, symbol: str, token: str) -> dict[str, float]:
        cache_key = f"ltp:{exchange}:{token}"
        r = self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

        raw = await self._get_quote(_MODE_LTP, exchange, symbol, token)
        result = {
            "ltp": _paise_to_rupees(raw.get("ltp")),
            "close": _paise_to_rupees(raw.get("close")),
            "token": token,
            "symbol": symbol,
            "exchange": exchange,
        }
        await r.set(cache_key, json.dumps(result), ex=1)
        return result

    async def get_full_quote(self, exchange: str, symbol: str, token: str) -> dict[str, Any]:
        cache_key = f"quote:{exchange}:{token}"
        r = self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

        raw = await self._get_quote(_MODE_FULL, exchange, symbol, token)
        result: dict[str, Any] = {
            "token": token,
            "symbol": symbol,
            "exchange": exchange,
            "ltp": _paise_to_rupees(raw.get("ltp")),
            "open": _paise_to_rupees(raw.get("open")),
            "high": _paise_to_rupees(raw.get("high")),
            "low": _paise_to_rupees(raw.get("low")),
            "close": _paise_to_rupees(raw.get("close")),
            "volume": int(raw.get("tradeVolume", 0) or 0),
            "avg_price": _paise_to_rupees(raw.get("avgPrice")),
            "oi": int(raw.get("opnInterest", 0) or 0),
            "upper_circuit": _paise_to_rupees(raw.get("upperCircuit")),
            "lower_circuit": _paise_to_rupees(raw.get("lowerCircuit")),
            "52w_high": _paise_to_rupees(raw.get("52WeekHigh")),
            "52w_low": _paise_to_rupees(raw.get("52WeekLow")),
            "depth": raw.get("depth", {}),
        }
        await r.set(cache_key, json.dumps(result), ex=5)
        return result

    async def get_ohlc(self, exchange: str, symbol: str, token: str) -> dict[str, float]:
        cache_key = f"ohlc:{exchange}:{token}"
        r = self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

        raw = await self._get_quote(_MODE_OHLC, exchange, symbol, token)
        result = {
            "token": token,
            "symbol": symbol,
            "exchange": exchange,
            "open": _paise_to_rupees(raw.get("open")),
            "high": _paise_to_rupees(raw.get("high")),
            "low": _paise_to_rupees(raw.get("low")),
            "close": _paise_to_rupees(raw.get("close")),
            "ltp": _paise_to_rupees(raw.get("ltp")),
        }
        await r.set(cache_key, json.dumps(result), ex=5)
        return result

    async def get_market_depth(self, exchange: str, symbol: str, token: str) -> dict[str, Any]:
        quote = await self.get_full_quote(exchange, symbol, token)
        return quote.get("depth", {})

    async def get_bulk_ltp(
        self, tokens_by_exchange: dict[str, list[str]]
    ) -> list[dict[str, Any]]:
        import httpx

        headers = await ANGEL_SESSION.get_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_BASE}/rest/secure/angelbroking/market/v1/quote/",
                json={"mode": _MODE_LTP, "exchangeTokens": tokens_by_exchange},
                headers=headers,
            )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"bulk ltp failed: {body.get('message')}")
        fetched = body.get("data", {}).get("fetched", [])
        result = []
        r = self._get_redis()
        pipe = r.pipeline()
        for raw in fetched:
            item = {
                "token": raw.get("symbolToken", ""),
                "symbol": raw.get("tradingSymbol", ""),
                "ltp": _paise_to_rupees(raw.get("ltp")),
                "close": _paise_to_rupees(raw.get("close")),
            }
            result.append(item)
            cache_key = f"ltp:{raw.get('exchType', '')}:{item['token']}"
            pipe.set(cache_key, json.dumps(item), ex=1)
        await pipe.execute()
        return result


MARKET_DATA = MarketDataService()
