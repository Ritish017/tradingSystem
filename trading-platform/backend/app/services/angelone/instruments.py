from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_DUMP_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
_DB_PATH = Path("/tmp/angelone_instruments.db")

_EXCHANGE_MAP = {
    "NSE": 1,
    "NFO": 2,
    "BSE": 3,
    "BFO": 4,
    "MCX": 5,
    "NCDEX": 7,
    "CDS": 13,
}


class InstrumentService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: redis.Redis | None = None
        self._lock = asyncio.Lock()
        self._loaded = False

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._redis

    def _init_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instruments (
                token TEXT,
                symbol TEXT,
                name TEXT,
                expiry TEXT,
                strike REAL,
                lotsize INTEGER,
                instrumenttype TEXT,
                exch_seg TEXT,
                tick_size REAL,
                PRIMARY KEY (token, exch_seg)
            )
            """
        )
        conn.commit()
        return conn

    async def download_and_cache(self) -> int:
        async with self._lock:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(_DUMP_URL)
                resp.raise_for_status()
                instruments: list[dict[str, Any]] = resp.json()

            conn = self._init_db()
            pipe = self._get_redis().pipeline()
            inserted = 0
            try:
                conn.execute("DELETE FROM instruments")
                for inst in instruments:
                    token = str(inst.get("token", ""))
                    symbol = str(inst.get("symbol", ""))
                    exch = str(inst.get("exch_seg", ""))
                    if not token or not symbol:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO instruments
                          (token, symbol, name, expiry, strike, lotsize, instrumenttype, exch_seg, tick_size)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            token,
                            symbol,
                            inst.get("name", ""),
                            inst.get("expiry", ""),
                            float(inst.get("strike", 0) or 0) / 100.0,
                            int(inst.get("lotsize", 1) or 1),
                            inst.get("instrumenttype", ""),
                            exch,
                            float(inst.get("tick_size", 0.05) or 0.05),
                        ),
                    )
                    # Redis: symbol→token lookup
                    redis_key = f"inst:sym:{exch}:{symbol}"
                    pipe.set(redis_key, token, ex=86400)
                    # Redis: token→full record
                    redis_tok_key = f"inst:tok:{exch}:{token}"
                    pipe.set(redis_tok_key, json.dumps(inst), ex=86400)
                    inserted += 1
                conn.commit()
                await pipe.execute()
            finally:
                conn.close()

            self._loaded = True
            logger.info("angelone_instruments_cached", count=inserted)
            return inserted

    async def ensure_loaded(self) -> None:
        if not self._loaded:
            # check SQLite first
            try:
                conn = sqlite3.connect(str(_DB_PATH))
                count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
                conn.close()
                if count > 0:
                    self._loaded = True
                    return
            except Exception:
                pass
            await self.download_and_cache()

    async def symbol_to_token(self, symbol: str, exchange: str = "NSE") -> str | None:
        await self.ensure_loaded()
        r = self._get_redis()
        token = await r.get(f"inst:sym:{exchange}:{symbol}")
        if token:
            return token
        # fallback to SQLite
        conn = sqlite3.connect(str(_DB_PATH))
        row = conn.execute(
            "SELECT token FROM instruments WHERE symbol=? AND exch_seg=?", (symbol, exchange)
        ).fetchone()
        conn.close()
        return row[0] if row else None

    async def token_to_info(self, token: str, exchange: str = "NSE") -> dict[str, Any] | None:
        r = self._get_redis()
        raw = await r.get(f"inst:tok:{exchange}:{token}")
        if raw:
            return json.loads(raw)
        conn = sqlite3.connect(str(_DB_PATH))
        row = conn.execute(
            "SELECT token,symbol,name,expiry,strike,lotsize,instrumenttype,exch_seg,tick_size "
            "FROM instruments WHERE token=? AND exch_seg=?",
            (token, exchange),
        ).fetchone()
        conn.close()
        if not row:
            return None
        keys = ["token", "symbol", "name", "expiry", "strike", "lotsize", "instrumenttype", "exch_seg", "tick_size"]
        return dict(zip(keys, row))

    async def search(self, query: str, exchange: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure_loaded()
        conn = sqlite3.connect(str(_DB_PATH))
        if exchange:
            rows = conn.execute(
                "SELECT token,symbol,name,expiry,strike,lotsize,instrumenttype,exch_seg,tick_size "
                "FROM instruments WHERE exch_seg=? AND (symbol LIKE ? OR name LIKE ?) LIMIT ?",
                (exchange, f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT token,symbol,name,expiry,strike,lotsize,instrumenttype,exch_seg,tick_size "
                "FROM instruments WHERE symbol LIKE ? OR name LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        conn.close()
        keys = ["token", "symbol", "name", "expiry", "strike", "lotsize", "instrumenttype", "exch_seg", "tick_size"]
        return [dict(zip(keys, r)) for r in rows]

    def exchange_type(self, exch_seg: str) -> int:
        return _EXCHANGE_MAP.get(exch_seg.upper(), 1)


INSTRUMENTS = InstrumentService()
