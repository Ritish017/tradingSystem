from __future__ import annotations

import json
from typing import Any, Literal

import httpx
import redis.asyncio as redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"

ExpiryType = Literal["NEAR", "NEXT", "FAR"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = await ANGEL_SESSION.get_headers()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("status"):
        raise RuntimeError(f"angelone options error: {body.get('message')}")
    return body


class OptionChainService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    async def get_option_chain(
        self,
        name: str,
        expiry_date: str,
        strike_price: float = 0.0,
        *,
        enrich_greeks: bool = True,
    ) -> dict[str, Any]:
        """
        name: underlying name e.g. "NIFTY", "BANKNIFTY", "RELIANCE"
        expiry_date: "DDMMMYYYY" e.g. "25JAN2024"
        strike_price: 0 = full chain
        """
        cache_key = f"optchain:{name}:{expiry_date}:{int(strike_price)}"
        r = self._get_redis()
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

        payload: dict[str, Any] = {
            "name": name,
            "expirydate": expiry_date,
        }
        if strike_price > 0:
            payload["strikeprice"] = str(strike_price)

        body = await _post(f"{_BASE}/rest/secure/angelbroking/market/v1/optionChain", payload)
        chain_data: dict[str, Any] = body.get("data", {}) or {}

        if enrich_greeks:
            chain_data = await self._enrich_with_greeks(chain_data)

        await r.set(cache_key, json.dumps(chain_data), ex=60)
        return chain_data

    async def _enrich_with_greeks(self, chain_data: dict[str, Any]) -> dict[str, Any]:
        from app.services.options.chain import enrich_chain_with_greeks

        try:
            return enrich_chain_with_greeks(chain_data)
        except Exception as exc:
            logger.warning("options_greeks_enrichment_failed", error=str(exc))
            return chain_data

    async def get_expiry_list(self, name: str, exchange: str = "NFO") -> list[str]:
        from app.services.angelone.instruments import INSTRUMENTS

        # Search for all option instruments matching the underlying name
        results = await INSTRUMENTS.search(f"{name}%", exchange=exchange)
        expiries = sorted({
            r["expiry"] for r in results
            if r.get("instrumenttype") in ("OPTSTK", "OPTIDX") and r.get("expiry")
        })
        return expiries


OPTION_CHAIN = OptionChainService()
