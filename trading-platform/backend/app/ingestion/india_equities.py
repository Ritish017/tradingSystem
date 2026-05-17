from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Protocol

import pandas as pd
import redis.asyncio as redis

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import MarketTick
from app.ingestion.publisher import TickPublisher

logger = get_logger(__name__)


class RedisLike(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None) -> bool | None: ...


HistoryFetcher = Callable[[str, date, date], pd.DataFrame]


class IndiaEquityIngestionService:
    def __init__(
        self,
        *,
        redis_client: RedisLike | None = None,
        publisher: TickPublisher | None = None,
        history_fetcher: HistoryFetcher | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings
        if resolved_settings is None and (redis_client is None or publisher is None):
            resolved_settings = get_settings()

        if redis_client is None:
            if resolved_settings is None:
                raise RuntimeError("settings or redis_client must be provided")
            self._redis = redis.from_url(resolved_settings.redis_url, decode_responses=True)
        else:
            self._redis = redis_client

        if publisher is None:
            self._publisher = TickPublisher(settings=resolved_settings)
        else:
            self._publisher = publisher
        self._history_fetcher = history_fetcher or self._fetch_symbol_history

    async def ingest_eod_row(
        self,
        symbol: str,
        close: float,
        volume: float,
        *,
        ts: datetime | None = None,
    ) -> MarketTick:
        tick = MarketTick(
            symbol=symbol,
            source="india_eod",
            price=close,
            volume=volume,
            ts=ts or datetime.now(UTC),
        )
        await self._publisher.publish_tick("ticks.india.eod", tick)
        await self._redis.set(f"tick:{symbol.upper()}", f"{tick.price}", ex=60)
        return tick

    async def ingest_symbol_history(self, symbol: str, start: date, end: date) -> int:
        frame = self._history_fetcher(symbol, start, end)
        rows = self._normalise_history_frame(frame)
        for row in rows:
            await self.ingest_eod_row(
                symbol=symbol,
                close=float(row["close"]),
                volume=float(row["volume"]),
                ts=row["ts"],
            )
        return len(rows)

    async def ingest_nse_universe(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, int]:
        output: dict[str, int] = {}
        for symbol in symbols:
            try:
                output[symbol] = await self.ingest_symbol_history(
                    symbol=symbol,
                    start=start,
                    end=end,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("nse_history_ingest_failed", symbol=symbol, error=str(exc))
                output[symbol] = 0
        return output

    def _fetch_symbol_history(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        try:
            frame = self._fetch_with_jugaad(symbol=symbol, start=start, end=end)
            if not frame.empty:
                return frame
        except Exception as exc:  # noqa: BLE001
            logger.warning("jugaad_fetch_failed", symbol=symbol, error=str(exc))
        return self._fetch_with_nsepy(symbol=symbol, start=start, end=end)

    @staticmethod
    def _fetch_with_jugaad(symbol: str, start: date, end: date) -> pd.DataFrame:
        from jugaad_data.nse import stock_df

        frame = stock_df(symbol=symbol, from_date=start, to_date=end, series="EQ")
        return pd.DataFrame(frame)

    @staticmethod
    def _fetch_with_nsepy(symbol: str, start: date, end: date) -> pd.DataFrame:
        from nsepy import get_history

        frame = get_history(symbol=symbol, start=start, end=end)
        return pd.DataFrame(frame)

    @staticmethod
    def _normalise_history_frame(frame: pd.DataFrame) -> list[dict[str, datetime | float]]:
        if frame.empty:
            return []
        normalised = frame.copy()
        normalised.columns = [str(column).strip().lower() for column in normalised.columns]

        close_col = IndiaEquityIngestionService._pick_column(
            normalised.columns,
            ("close", "adj close", "adj_close", "last", "ltp"),
        )
        volume_col = IndiaEquityIngestionService._pick_column(
            normalised.columns,
            ("volume", "tottrdqty", "ttl_trd_qnty", "totaltradedquantity"),
        )
        date_col = IndiaEquityIngestionService._pick_column(
            normalised.columns,
            ("date", "timestamp", "datetime"),
        )
        if close_col is None or volume_col is None:
            raise ValueError("History frame must contain close and volume columns")

        if date_col is None:
            ts_series = pd.to_datetime(normalised.index, utc=True, errors="coerce")
        else:
            ts_series = pd.to_datetime(normalised[date_col], utc=True, errors="coerce")

        clean = pd.DataFrame(
            {
                "ts": ts_series,
                "close": pd.to_numeric(normalised[close_col], errors="coerce"),
                "volume": pd.to_numeric(normalised[volume_col], errors="coerce"),
            }
        ).dropna(subset=["ts", "close", "volume"])

        return [
            {
                "ts": row.ts.to_pydatetime().astimezone(UTC),
                "close": float(row.close),
                "volume": float(row.volume),
            }
            for row in clean.itertuples(index=False)
        ]

    @staticmethod
    def _pick_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
        lower_map = {column.lower(): column for column in columns}
        for candidate in candidates:
            if candidate in lower_map:
                return lower_map[candidate]
        return None

