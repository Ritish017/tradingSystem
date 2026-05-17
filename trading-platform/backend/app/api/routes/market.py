from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.engine.tick_aggregator import TICK_AGGREGATOR
from app.services.angelone.historical import HISTORICAL, Interval
from app.services.angelone.instruments import INSTRUMENTS
from app.services.angelone.marketdata import MARKET_DATA

router = APIRouter(prefix="/v1/market", tags=["market"])


@router.get("/quote")
async def get_quote(
    symbol: str = Query(..., description="Trading symbol e.g. RELIANCE"),
    exchange: str = Query("NSE", description="Exchange: NSE, BSE, NFO, MCX"),
    token: str | None = Query(None, description="Symbol token (resolved if omitted)"),
) -> dict[str, Any]:
    if token is None:
        token = await INSTRUMENTS.symbol_to_token(symbol, exchange)
        if token is None:
            raise HTTPException(404, f"Symbol {symbol} not found on {exchange}")
    try:
        return await MARKET_DATA.get_full_quote(exchange, symbol, token)
    except Exception as exc:
        raise HTTPException(502, f"Quote fetch failed: {exc}") from exc


@router.get("/ltp")
async def get_ltp(
    symbol: str = Query(...),
    exchange: str = Query("NSE"),
    token: str | None = Query(None),
) -> dict[str, Any]:
    if token is None:
        token = await INSTRUMENTS.symbol_to_token(symbol, exchange)
        if token is None:
            raise HTTPException(404, f"Symbol {symbol} not found on {exchange}")
    try:
        return await MARKET_DATA.get_ltp(exchange, symbol, token)
    except Exception as exc:
        raise HTTPException(502, f"LTP fetch failed: {exc}") from exc


@router.get("/depth")
async def get_depth(
    symbol: str = Query(...),
    exchange: str = Query("NSE"),
    token: str | None = Query(None),
) -> dict[str, Any]:
    if token is None:
        token = await INSTRUMENTS.symbol_to_token(symbol, exchange)
        if token is None:
            raise HTTPException(404, f"Symbol {symbol} not found on {exchange}")
    try:
        return await MARKET_DATA.get_market_depth(exchange, symbol, token)
    except Exception as exc:
        raise HTTPException(502, f"Depth fetch failed: {exc}") from exc


@router.get("/candles")
async def get_candles(
    symbol: str = Query(...),
    exchange: str = Query("NSE"),
    timeframe: str = Query("1m", description="1m | 5m | 15m | 1h"),
    limit: int = Query(100, ge=1, le=1000),
    token: str | None = Query(None),
) -> list[dict[str, Any]]:
    # Try live aggregator first (real-time candles)
    live = await TICK_AGGREGATOR.get_candles(symbol, timeframe, limit)
    if live:
        return live

    # Fall back to Angel One historical API
    if token is None:
        token = await INSTRUMENTS.symbol_to_token(symbol, exchange)
        if token is None:
            raise HTTPException(404, f"Symbol {symbol} not found on {exchange}")

    tf_map: dict[str, Interval] = {
        "1m": "ONE_MINUTE",
        "3m": "THREE_MINUTE",
        "5m": "FIVE_MINUTE",
        "10m": "TEN_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE",
        "1h": "ONE_HOUR",
        "1d": "ONE_DAY",
    }
    interval = tf_map.get(timeframe, "ONE_MINUTE")
    days_map = {"1m": 5, "5m": 20, "15m": 60, "1h": 180, "1d": 365}
    days = days_map.get(timeframe, 5)

    from datetime import UTC, datetime, timedelta
    to_dt = datetime.now(UTC)
    from_dt = to_dt - timedelta(days=days)

    try:
        candles = await HISTORICAL.get_candles(exchange, token, interval, from_dt, to_dt)
        return candles[-limit:]
    except Exception as exc:
        raise HTTPException(502, f"Historical fetch failed: {exc}") from exc


@router.get("/search")
async def search_instruments(
    query: str = Query(..., min_length=2),
    exchange: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> list[dict[str, Any]]:
    return await INSTRUMENTS.search(query, exchange=exchange, limit=limit)


@router.get("/ohlc")
async def get_ohlc(
    symbol: str = Query(...),
    exchange: str = Query("NSE"),
    token: str | None = Query(None),
) -> dict[str, Any]:
    if token is None:
        token = await INSTRUMENTS.symbol_to_token(symbol, exchange)
        if token is None:
            raise HTTPException(404, f"Symbol {symbol} not found on {exchange}")
    try:
        return await MARKET_DATA.get_ohlc(exchange, symbol, token)
    except Exception as exc:
        raise HTTPException(502, f"OHLC fetch failed: {exc}") from exc
