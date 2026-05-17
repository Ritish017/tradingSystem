"""Shared Redpanda helpers for the hybrid engine.

All services use the Redpanda REST Proxy (HTTP) so no aiokafka binary
dependency is required — the same httpx client already used by TickPublisher.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

TOPICS = [
    "market_ticks",
    "raw_news",
    "macro_data",
    "normalized_data",
    "features",
    "news_signals",
    "unified_signal",
]


async def ensure_topics() -> None:
    """Create all hybrid-engine topics via Redpanda Admin API (idempotent)."""
    base = str(settings.redpanda_proxy_url).rstrip("/")
    # Use the Kafka REST Proxy topic-creation endpoint
    async with httpx.AsyncClient(timeout=10) as client:
        for topic in TOPICS:
            try:
                resp = await client.post(
                    f"{base}/topics",
                    json={"topic_name": topic, "partitions_count": 1, "replication_factor": 1},
                    headers={"Content-Type": "application/vnd.kafka.v2+json"},
                )
                if resp.status_code not in {200, 201, 409}:  # 409 = already exists
                    logger.warning("topic_create_warn", topic=topic, status=resp.status_code)
            except Exception as exc:
                logger.warning("topic_create_error", topic=topic, error=str(exc))


async def publish(topic: str, payload: dict[str, Any]) -> None:
    """Publish a single JSON record to a Redpanda topic via REST Proxy."""
    base = str(settings.redpanda_proxy_url).rstrip("/")
    body = {"records": [{"value": payload}]}
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.post(
                f"{base}/topics/{topic}",
                json=body,
                headers={"Content-Type": "application/vnd.kafka.json.v2+json"},
            )
            if resp.status_code >= 400:
                logger.warning("publish_failed", topic=topic, status=resp.status_code)
        except Exception as exc:
            logger.error("publish_error", topic=topic, error=str(exc))


async def consume(
    topic: str,
    group_id: str,
    consumer_id: str,
    poll_interval: float = 1.0,
) -> AsyncIterator[dict[str, Any]]:
    """Long-poll consumer using Redpanda REST Proxy consumer groups."""
    base = str(settings.redpanda_proxy_url).rstrip("/")
    consumer_url = f"{base}/consumers/{group_id}"
    instance_url: str | None = None

    async with httpx.AsyncClient(timeout=30) as client:
        # Create consumer instance
        try:
            resp = await client.post(
                consumer_url,
                json={"name": consumer_id, "format": "json", "auto.offset.reset": "latest"},
                headers={"Content-Type": "application/vnd.kafka.v2+json"},
            )
            if resp.status_code not in {200, 409}:
                logger.error("consumer_create_failed", group=group_id, status=resp.status_code)
                return
            data = resp.json()
            instance_url = data.get("base_uri", f"{consumer_url}/instances/{consumer_id}")
        except Exception as exc:
            logger.error("consumer_create_error", error=str(exc))
            return

        # Subscribe to topic
        try:
            await client.post(
                f"{instance_url}/subscription",
                json={"topics": [topic]},
                headers={"Content-Type": "application/vnd.kafka.v2+json"},
            )
        except Exception as exc:
            logger.error("consumer_subscribe_error", error=str(exc))
            return

        # Poll loop
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
                logger.warning("consumer_poll_error", topic=topic, error=str(exc))
                await asyncio.sleep(poll_interval)
            await asyncio.sleep(poll_interval)
