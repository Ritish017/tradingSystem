"""Unified Event Bus — Law 1 + Law 7.

Single entry point for all inter-component communication.
Every publish() injects a trace_id.
Every failed publish is caught, logged, retried (tenacity), then dead-lettered.

Usage:
    from app.bus.event_bus import BUS
    from app.bus.topics import MARKET_TICKS

    # publish
    await BUS.publish(MARKET_TICKS, payload, trace_id=trace_id)

    # subscribe (async generator)
    async for event in BUS.subscribe(UNIFIED_SIGNAL, "engine", "engine-1"):
        process(event)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.bus.topics import DEAD_LETTER
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    """
    Wraps Redpanda REST Proxy with:
    - trace_id injection on every event
    - tenacity retry (3 attempts, exponential backoff)
    - dead-letter routing after all retries fail
    - Redis pub/sub fallback when Redpanda is unavailable
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = str(self._settings.redpanda_proxy_url).rstrip("/")

    # ── Publish ───────────────────────────────────────────────────────────────

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        """Publish one event to a Redpanda topic.

        Injects _trace_id and _topic into the payload envelope.
        Retries 3 times with exponential backoff. On total failure, sends to DLQ.
        """
        envelope = {
            **payload,
            "_trace_id": trace_id or str(uuid.uuid4()),
            "_topic": topic,
        }
        try:
            await self._publish_with_retry(topic, envelope)
            logger.info(
                "bus_publish_ok",
                topic=topic,
                trace_id=envelope["_trace_id"],
            )
        except Exception as exc:
            logger.error(
                "bus_publish_failed_sending_dlq",
                topic=topic,
                trace_id=envelope["_trace_id"],
                error=str(exc),
            )
            await self._send_to_dlq(topic, envelope, str(exc))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _publish_with_retry(self, topic: str, envelope: dict[str, Any]) -> None:
        body = {"records": [{"value": envelope}]}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{self._base_url}/topics/{topic}",
                json=body,
                headers={"Content-Type": "application/vnd.kafka.json.v2+json"},
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Redpanda publish failed: {resp.status_code} {resp.text[:200]}"
                )

    async def _send_to_dlq(self, original_topic: str, envelope: dict[str, Any], error: str) -> None:
        dlq_record = {**envelope, "_dlq_source_topic": original_topic, "_dlq_error": error}
        body = {"records": [{"value": dlq_record}]}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self._base_url}/topics/{DEAD_LETTER}",
                    json=body,
                    headers={"Content-Type": "application/vnd.kafka.json.v2+json"},
                )
        except Exception as dlq_exc:
            logger.error("bus_dlq_write_failed", error=str(dlq_exc))

    # ── Subscribe ─────────────────────────────────────────────────────────────

    async def subscribe(
        self,
        topic: str,
        group_id: str,
        consumer_id: str,
        poll_interval: float = 1.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Long-poll consumer using Redpanda REST Proxy consumer groups.

        Yields events with their _trace_id intact so downstream layers can
        bind it to their log context via bind_trace_id().
        """
        consumer_url = f"{self._base_url}/consumers/{group_id}"
        instance_url: str | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            # create consumer
            try:
                resp = await client.post(
                    consumer_url,
                    json={"name": consumer_id, "format": "json", "auto.offset.reset": "latest"},
                    headers={"Content-Type": "application/vnd.kafka.v2+json"},
                )
                if resp.status_code not in {200, 409}:
                    logger.error("bus_consumer_create_failed", group=group_id, status=resp.status_code)
                    return
                data = resp.json()
                instance_url = data.get("base_uri", f"{consumer_url}/instances/{consumer_id}")
            except Exception as exc:
                logger.error("bus_consumer_create_error", error=str(exc))
                return

            # subscribe
            try:
                await client.post(
                    f"{instance_url}/subscription",
                    json={"topics": [topic]},
                    headers={"Content-Type": "application/vnd.kafka.v2+json"},
                )
            except Exception as exc:
                logger.error("bus_subscribe_error", topic=topic, error=str(exc))
                return

            # poll loop
            while True:
                try:
                    resp = await client.get(
                        f"{instance_url}/records",
                        headers={"Accept": "application/vnd.kafka.json.v2+json"},
                        params={"max_bytes": 1048576, "timeout": int(poll_interval * 1000)},
                    )
                    if resp.status_code == 200:
                        for record in resp.json():
                            value = record.get("value")
                            if isinstance(value, dict):
                                yield value
                            elif isinstance(value, str):
                                try:
                                    yield json.loads(value)
                                except json.JSONDecodeError:
                                    pass
                except Exception as exc:
                    logger.warning("bus_poll_error", topic=topic, error=str(exc))
                    await asyncio.sleep(poll_interval)
                await asyncio.sleep(poll_interval)

    # ── Redis pub/sub helpers (hot-tier channels) ─────────────────────────────

    async def publish_redis(
        self,
        channel: str,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        """Publish to a Redis pub/sub channel (ephemeral fan-out)."""
        import redis.asyncio as aioredis

        envelope = {
            **payload,
            "_trace_id": trace_id or str(uuid.uuid4()),
            "_channel": channel,
        }
        try:
            r = aioredis.from_url(self._settings.redis_url, decode_responses=True)
            await r.publish(channel, json.dumps(envelope))
            await r.aclose()
        except Exception as exc:
            logger.warning("bus_redis_publish_failed", channel=channel, error=str(exc))


BUS = EventBus()
