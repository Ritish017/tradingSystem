from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd
import pytest

from app.ingestion.india_equities import IndiaEquityIngestionService


class TickLike(Protocol):
    symbol: str
    price: float


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, int | None]] = {}

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self.values[name] = (value, ex)
        return True


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    async def publish_tick(self, topic: str, tick: TickLike) -> None:
        self.calls.append((topic, tick.symbol, float(tick.price)))


def fake_history_fetcher(symbol: str, start: date, end: date) -> pd.DataFrame:
    del symbol, start, end
    return pd.DataFrame(
        {
            "DATE": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "CLOSE": [100.0, 101.5, 102.25],
            "VOLUME": [1_000_000, 1_200_000, 900_000],
        }
    )


@pytest.mark.asyncio
async def test_ingest_symbol_history_publishes_each_row_and_updates_cache() -> None:
    redis_client = FakeRedis()
    publisher = FakePublisher()
    service = IndiaEquityIngestionService(
        redis_client=redis_client,
        publisher=publisher,
        history_fetcher=fake_history_fetcher,
    )
    rows = await service.ingest_symbol_history("RELIANCE", date(2024, 1, 1), date(2024, 1, 3))
    assert rows == 3
    assert len(publisher.calls) == 3
    assert publisher.calls[0] == ("ticks.india.eod", "RELIANCE", 100.0)
    assert redis_client.values["tick:RELIANCE"] == ("102.25", 60)
