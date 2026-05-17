from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncpg
import httpx
import redis.asyncio as redis

from app.core.config import Settings


@dataclass(frozen=True)
class ServiceHealth:
    status: str
    detail: str | None = None


class HealthChecker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check_postgres(self) -> ServiceHealth:
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=self._settings.database_url.replace("+asyncpg", "")),
                timeout=1.5,
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return ServiceHealth(status="ok")
        except Exception as exc:  # noqa: BLE001
            return ServiceHealth(status="error", detail=str(exc))

    async def check_redis(self) -> ServiceHealth:
        client = redis.from_url(self._settings.redis_url, decode_responses=True, socket_connect_timeout=1.5)
        try:
            pong = await asyncio.wait_for(client.ping(), timeout=1.5)
            if pong is True:
                return ServiceHealth(status="ok")
            return ServiceHealth(status="error", detail="unexpected ping response")
        except Exception as exc:  # noqa: BLE001
            return ServiceHealth(status="error", detail=str(exc))
        finally:
            await client.aclose()

    async def check_influxdb(self) -> ServiceHealth:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{self._settings.influxdb_url}/health")
            if response.status_code == 200:
                return ServiceHealth(status="ok")
            return ServiceHealth(status="error", detail=f"http {response.status_code}")
        except Exception as exc:  # noqa: BLE001
            return ServiceHealth(status="error", detail=str(exc))

    async def check_redpanda(self) -> ServiceHealth:
        host, port = self._settings.redpanda_brokers.split(",")[0].split(":")
        try:
            conn = asyncio.open_connection(host, int(port))
            reader, writer = await asyncio.wait_for(conn, timeout=1.5)
            writer.close()
            await writer.wait_closed()
            del reader
            return ServiceHealth(status="ok")
        except Exception as exc:  # noqa: BLE001
            return ServiceHealth(status="error", detail=str(exc))

    async def check_mlflow(self) -> ServiceHealth:
        return await self._check_http(str(self._settings.mlflow_tracking_uri))

    async def check_openalgo(self) -> ServiceHealth:
        return await self._check_http(str(self._settings.openalgo_base_url))

    async def check_grafana(self) -> ServiceHealth:
        return await self._check_http(str(self._settings.grafana_url))

    async def _check_http(self, url: str) -> ServiceHealth:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(url)
            if response.status_code < 500:
                return ServiceHealth(status="ok")
            return ServiceHealth(status="error", detail=f"http {response.status_code}")
        except Exception as exc:  # noqa: BLE001
            return ServiceHealth(status="error", detail=str(exc))

