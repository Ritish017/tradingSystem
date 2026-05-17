from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.metrics import TICK_PUBLISH_FAILURES_TOTAL, TICKS_INGESTED_TOTAL
from app.core.types import MarketTick


class TickPublisher:
    """Publish ticks to Redpanda + InfluxDB, with an in-memory shadow for tests/debug."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        enable_external_publish: bool | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http_client = http_client or httpx.AsyncClient(timeout=5.0)
        self._owns_client = http_client is None
        self._enable_external_publish = (
            self._settings.publish_ticks_to_external
            if enable_external_publish is None
            else enable_external_publish
        )
        self._topic_payloads: dict[str, list[str]] = {}

    async def publish_tick(self, topic: str, tick: MarketTick) -> None:
        payload = json.dumps(asdict(tick), default=str)
        self._topic_payloads.setdefault(topic, []).append(payload)
        TICKS_INGESTED_TOTAL.labels(source=tick.source, symbol=tick.symbol).inc()
        if not self._enable_external_publish:
            return
        publish_tasks = [
            self._publish_to_redpanda(topic=topic, payload=payload),
            self._write_to_influx(tick=tick),
        ]
        try:
            await asyncio.gather(*publish_tasks)
        except Exception:  # noqa: BLE001
            TICK_PUBLISH_FAILURES_TOTAL.labels(source=tick.source).inc()
            raise

    def last_payload(self, topic: str) -> str | None:
        bucket = self._topic_payloads.get(topic, [])
        return bucket[-1] if bucket else None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def _publish_to_redpanda(self, topic: str, payload: str) -> None:
        base_url = str(self._settings.redpanda_proxy_url).rstrip("/")
        body: dict[str, Any] = {"records": [{"value": json.loads(payload)}]}
        response = await self._http_client.post(
            f"{base_url}/topics/{topic}",
            json=body,
            headers={"Content-Type": "application/vnd.kafka.json.v2+json"},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"redpanda publish failed ({response.status_code}): {response.text}")

    async def _write_to_influx(self, tick: MarketTick) -> None:
        influx_url = str(self._settings.influxdb_url).rstrip("/")
        line = self._line_protocol(tick)
        response = await self._http_client.post(
            f"{influx_url}/api/v2/write",
            params={
                "org": self._settings.influxdb_org,
                "bucket": self._settings.influxdb_bucket,
                "precision": "ms",
            },
            content=line,
            headers={"Authorization": f"Token {self._settings.influxdb_token}"},
        )
        if response.status_code not in {202, 204}:
            raise RuntimeError(f"influx write failed ({response.status_code}): {response.text}")

    @staticmethod
    def _line_protocol(tick: MarketTick) -> str:
        symbol = TickPublisher._escape_tag(tick.symbol)
        source = TickPublisher._escape_tag(tick.source)
        timestamp_ms = int(tick.ts.timestamp() * 1000)
        return (
            f"ticks,symbol={symbol},source={source} "
            f"price={tick.price},volume={tick.volume} {timestamp_ms}"
        )

    @staticmethod
    def _escape_tag(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace(",", "\\,")
            .replace(" ", "\\ ")
            .replace("=", "\\=")
        )

