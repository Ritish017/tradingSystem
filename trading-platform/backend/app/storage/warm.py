"""Warm-tier storage — Law 6.

Queried by time range. Used for: candles, order book snapshots, options data.
Backed by InfluxDB (raw ticks) and TimescaleDB (OHLCV candles, option snapshots).

Rule: if you need "give me data between T1 and T2", it goes here.
Never use warm tier for the current state of an open order or position.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class WarmStore:
    def __init__(self) -> None:
        self._settings = get_settings()

    # ── InfluxDB: raw tick writes ─────────────────────────────────────────────

    async def write_tick(self, symbol: str, source: str, price: float, volume: float, ts: datetime) -> None:
        """Write a single tick to InfluxDB in line protocol format."""
        influx_url = str(self._settings.influxdb_url).rstrip("/")
        sym = self._escape(symbol)
        src = self._escape(source)
        timestamp_ms = int(ts.timestamp() * 1000)
        line = (
            f"ticks,symbol={sym},source={src} "
            f"price={price},volume={volume} {timestamp_ms}"
        )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{influx_url}/api/v2/write",
                    params={
                        "org": self._settings.influxdb_org,
                        "bucket": self._settings.influxdb_bucket,
                        "precision": "ms",
                    },
                    content=line,
                    headers={"Authorization": f"Token {self._settings.influxdb_token}"},
                )
                if resp.status_code not in {202, 204}:
                    logger.warning("warm_influx_write_failed", symbol=symbol, status=resp.status_code)
        except Exception as exc:
            logger.warning("warm_influx_write_error", symbol=symbol, error=str(exc))

    # ── TimescaleDB: OHLCV candle writes ─────────────────────────────────────

    async def write_candle(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        ts: datetime,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """Upsert a completed candle bar into TimescaleDB."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self._settings.database_url.replace("+asyncpg", ""))
            await conn.execute(
                """
                INSERT INTO candles (symbol, exchange, timeframe, ts, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (symbol, timeframe, ts) DO UPDATE
                SET high = GREATEST(candles.high, EXCLUDED.high),
                    low  = LEAST(candles.low, EXCLUDED.low),
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """,
                symbol, exchange, timeframe, ts, open_, high, low, close, volume,
            )
            await conn.close()
        except Exception as exc:
            logger.warning("warm_candle_write_error", symbol=symbol, timeframe=timeframe, error=str(exc))

    # ── TimescaleDB: option snapshot writes ───────────────────────────────────

    async def write_option_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Insert an option chain snapshot row into TimescaleDB."""
        try:
            import asyncpg
            conn = await asyncpg.connect(self._settings.database_url.replace("+asyncpg", ""))
            await conn.execute(
                """
                INSERT INTO option_snapshots
                  (symbol, expiry, strike, option_type, ltp, oi, oi_change, iv, delta, gamma, theta, vega)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                snapshot.get("symbol"),
                snapshot.get("expiry"),
                snapshot.get("strike"),
                snapshot.get("option_type"),
                snapshot.get("ltp"),
                snapshot.get("oi"),
                snapshot.get("oi_change"),
                snapshot.get("iv"),
                snapshot.get("delta"),
                snapshot.get("gamma"),
                snapshot.get("theta"),
                snapshot.get("vega"),
            )
            await conn.close()
        except Exception as exc:
            logger.warning("warm_option_snapshot_error", error=str(exc))

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")


WARM = WarmStore()
