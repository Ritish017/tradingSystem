"""Hybrid Signals API Route

Endpoints:
  GET  /api/hybrid/signals          → latest signal per asset (from Redis)
  GET  /api/hybrid/signals/{asset}  → latest signal for specific asset
  GET  /api/hybrid/health           → service health check
  POST /api/hybrid/signals/consume  → manually trigger fusion for an asset (testing)
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/hybrid", tags=["hybrid"])
logger = get_logger(__name__)
settings = get_settings()

_TRACKED_ASSETS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "NIFTY50", "BANKNIFTY", "GOLD", "SILVER", "BTCUSDT", "ETHUSDT",
]


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


@router.get("/signals")
async def get_all_signals() -> dict[str, Any]:
    """Return latest unified_signal for all tracked assets."""
    redis = await _get_redis()
    try:
        signals = {}
        for asset in _TRACKED_ASSETS:
            raw = await redis.get(f"signal:{asset}")
            if raw:
                try:
                    signals[asset] = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        return {"signals": signals, "count": len(signals)}
    finally:
        await redis.aclose()


@router.get("/signals/{asset}")
async def get_signal(asset: str) -> dict[str, Any]:
    """Return latest unified_signal for a specific asset."""
    asset = asset.upper()
    redis = await _get_redis()
    try:
        raw = await redis.get(f"signal:{asset}")
        if not raw:
            raise HTTPException(status_code=404, detail=f"No signal found for {asset}")
        return json.loads(raw)
    finally:
        await redis.aclose()


@router.get("/health")
async def hybrid_health() -> dict[str, Any]:
    """Check how many assets have fresh signals."""
    redis = await _get_redis()
    try:
        fresh = 0
        stale = 0
        for asset in _TRACKED_ASSETS:
            ttl = await redis.ttl(f"signal:{asset}")
            if ttl > 0:
                fresh += 1
            else:
                stale += 1
        return {
            "status": "ok" if fresh > 0 else "degraded",
            "fresh_signals": fresh,
            "stale_signals": stale,
            "tracked_assets": len(_TRACKED_ASSETS),
        }
    finally:
        await redis.aclose()
