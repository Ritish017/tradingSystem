from __future__ import annotations

from typing import Any

import httpx
import redis.asyncio as redis
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def _get(url: str) -> dict[str, Any]:
    headers = await ANGEL_SESSION.get_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


class PortfolioService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    async def get_holdings(self) -> list[dict[str, Any]]:
        body = await _get(f"{_BASE}/rest/secure/angelbroking/portfolio/v1/getAllHolding")
        holdings = body.get("data", {})
        if isinstance(holdings, dict):
            holdings = holdings.get("holdings", [])
        return holdings or []

    async def get_positions(self) -> list[dict[str, Any]]:
        body = await _get(f"{_BASE}/rest/secure/angelbroking/order/v1/getPosition")
        return body.get("data", []) or []

    async def get_funds(self) -> dict[str, Any]:
        body = await _get(f"{_BASE}/rest/secure/angelbroking/user/v1/getRMS")
        return body.get("data", {}) or {}

    async def compute_pnl(self) -> dict[str, float]:
        positions = await self.get_positions()
        realized = 0.0
        unrealized = 0.0
        for pos in positions:
            try:
                realised_val = float(pos.get("realisedprofitloss", 0) or 0)
                unrealised_val = float(pos.get("unrealisedprofitloss", 0) or 0)
                realized += realised_val
                unrealized += unrealised_val
            except (TypeError, ValueError):
                continue
        return {
            "realized": realized,
            "unrealized": unrealized,
            "total": realized + unrealized,
        }

    async def get_holdings_with_ltp(self) -> list[dict[str, Any]]:
        from app.services.angelone.marketdata import MARKET_DATA

        holdings = await self.get_holdings()
        enriched = []
        for h in holdings:
            token = str(h.get("symboltoken", ""))
            symbol = str(h.get("tradingsymbol", ""))
            exchange = str(h.get("exchange", "NSE"))
            try:
                ltp_data = await MARKET_DATA.get_ltp(exchange, symbol, token)
                ltp = ltp_data["ltp"]
            except Exception:
                ltp = float(h.get("ltp", 0) or 0)
            avg_cost = float(h.get("averageprice", 0) or 0)
            qty = int(h.get("quantity", 0) or 0)
            current_val = ltp * qty
            invested_val = avg_cost * qty
            enriched.append(
                {
                    **h,
                    "live_ltp": ltp,
                    "current_value": current_val,
                    "invested_value": invested_val,
                    "unrealized_pnl": current_val - invested_val,
                    "pnl_pct": ((ltp - avg_cost) / avg_cost * 100) if avg_cost else 0.0,
                }
            )
        return enriched


PORTFOLIO = PortfolioService()
