from __future__ import annotations

from typing import Protocol

import pytest

from app.ingestion.india_kite_ws import KiteTickIngestionService


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


@pytest.mark.asyncio
async def test_kite_feature_flag_blocks_ticks_when_disabled() -> None:
    service = KiteTickIngestionService(
        enabled=False,
        redis_client=FakeRedis(),
        publisher=FakePublisher(),
    )
    with pytest.raises(RuntimeError):
        await service.handle_kite_tick("NIFTY 50", 22000.0, 10.0)


@pytest.mark.asyncio
async def test_kite_payload_handler_publishes_tick_when_enabled() -> None:
    redis_client = FakeRedis()
    publisher = FakePublisher()
    service = KiteTickIngestionService(enabled=True, redis_client=redis_client, publisher=publisher)

    tick = await service.handle_kite_tick_payload(
        {
            "tradingsymbol": "NIFTY 50",
            "last_price": 22015.5,
            "volume": 1250,
            "timestamp": "2026-05-14T09:30:00Z",
        }
    )
    assert tick.symbol == "NIFTY 50"
    assert tick.price == pytest.approx(22015.5)
    assert publisher.calls == [("ticks.india.live", "NIFTY 50", 22015.5)]
    assert redis_client.values["tick:NIFTY 50"] == ("22015.5", 60)
