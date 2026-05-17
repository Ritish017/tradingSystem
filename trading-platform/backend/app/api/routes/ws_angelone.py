from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(tags=["ws-v1"])
logger = get_logger(__name__)

_settings = get_settings()


def _get_redis() -> redis.Redis:
    return redis.from_url(_settings.redis_url, decode_responses=True)


@router.websocket("/api/v1/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
    """
    Streams live market ticks to frontend.
    Subscribes to Redis pub/sub channels: ticks:india + ticks:crypto
    Optional query param ?symbols=RELIANCE,TCS to filter symbols.
    """
    await websocket.accept()
    symbols_raw = websocket.query_params.get("symbols", "")
    filter_symbols = {s.strip().upper() for s in symbols_raw.split(",") if s.strip()} if symbols_raw else set()

    r = _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("ticks:india", "ticks:crypto")
    logger.info("ws_ticks_client_connected", filter=filter_symbols or "all")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data: dict[str, Any] = json.loads(message["data"])
                if filter_symbols and data.get("symbol", "").upper() not in filter_symbols:
                    continue
                await websocket.send_json(data)
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.warning("ws_ticks_send_error", error=str(exc))
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("ticks:india", "ticks:crypto")
        await pubsub.aclose()
        await r.aclose()
        logger.info("ws_ticks_client_disconnected")


@router.websocket("/api/v1/ws/orders")
async def ws_orders(websocket: WebSocket) -> None:
    """
    Streams live order update events to frontend via Redis pub/sub.
    Angel One order stream publishes to Redis channel "order_updates".
    """
    await websocket.accept()
    r = _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("order_updates")
    logger.info("ws_orders_client_connected")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data: dict[str, Any] = json.loads(message["data"])
                await websocket.send_json(data)
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.warning("ws_orders_send_error", error=str(exc))
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("order_updates")
        await pubsub.aclose()
        await r.aclose()
        logger.info("ws_orders_client_disconnected")


@router.websocket("/api/v1/ws/candles")
async def ws_candles(websocket: WebSocket) -> None:
    """
    Streams completed OHLC candle bars. ?timeframe=1m|5m|15m|1h
    """
    await websocket.accept()
    timeframe = websocket.query_params.get("timeframe", "1m")
    channel = f"candles:{timeframe}"
    r = _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    logger.info("ws_candles_client_connected", timeframe=timeframe)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                await websocket.send_text(message["data"])
            except WebSocketDisconnect:
                break
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await r.aclose()
