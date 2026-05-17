from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

import pytest

from app.ingestion.crypto_ccxt import CryptoTickIngestionService


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
        self.published: list[tuple[str, str, float]] = []

    async def publish_tick(self, topic: str, tick: TickLike) -> None:
        self.published.append((topic, tick.symbol, float(tick.price)))


class FakeSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = messages

    async def recv(self) -> str:
        if not self._messages:
            raise RuntimeError("no more messages")
        return self._messages.pop(0)


def socket_factory(messages: list[str], observed_urls: list[str]):
    @asynccontextmanager
    async def _connect(url: str) -> AsyncIterator[FakeSocket]:
        observed_urls.append(url)
        yield FakeSocket(messages)

    return _connect


def test_parse_binance_message_uses_event_time() -> None:
    tick = CryptoTickIngestionService.parse_binance_message(
        {"s": "BTCUSDT", "c": "66000.5", "v": "10.5", "E": 1_710_000_000_000}
    )
    assert tick.symbol == "BTCUSDT"
    assert tick.price == pytest.approx(66000.5)
    assert tick.volume == pytest.approx(10.5)
    assert tick.ts.year >= 2024


@pytest.mark.asyncio
async def test_stream_binance_tickers_publishes_and_updates_cache() -> None:
    observed_urls: list[str] = []
    redis_client = FakeRedis()
    publisher = FakePublisher()
    messages = [
        json.dumps(
            {
                "stream": "btcusdt@ticker",
                "data": {"s": "BTCUSDT", "c": "65000.1", "v": "2.3", "E": 1_710_000_000_000},
            }
        ),
        json.dumps(
            {
                "stream": "ethusdt@ticker",
                "data": {"s": "ETHUSDT", "c": "3200.5", "v": "15.1", "E": 1_710_000_010_000},
            }
        ),
    ]
    service = CryptoTickIngestionService(
        redis_client=redis_client,
        publisher=publisher,
        websocket_connect=socket_factory(messages, observed_urls),
        binance_ws_url="wss://example.test/stream",
    )
    await service.stream_binance_tickers(["BTC/USDT", "ETH/USDT"], message_limit=2)

    assert observed_urls == ["wss://example.test/stream?streams=btcusdt@ticker/ethusdt@ticker"]
    assert publisher.published == [
        ("ticks.crypto", "BTCUSDT", 65000.1),
        ("ticks.crypto", "ETHUSDT", 3200.5),
    ]
    assert redis_client.values["tick:BTCUSDT"] == ("65000.1", 60)
    assert redis_client.values["tick:ETHUSDT"] == ("3200.5", 60)
