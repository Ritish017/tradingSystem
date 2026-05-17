from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pyotp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"


class AngelOneSession:
    """Singleton JWT session manager — auto-login via TOTP, silent refresh."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._lock = asyncio.Lock()
        self._jwt: str | None = None
        self._refresh_token: str | None = None
        self._feed_token: str | None = None
        self._expires_at: datetime | None = None
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_headers(self) -> dict[str, str]:
        return {
            "X-PrivateKey": self._settings.angel_api_key,
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "fe:80:00:00:00:00",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        return {**self._base_headers(), "Authorization": f"Bearer {self._jwt}"}

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    # ------------------------------------------------------------------
    # Login / refresh
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _do_login(self) -> None:
        totp = pyotp.TOTP(self._settings.angel_totp_secret).now()
        client = await self._client_get()
        resp = await client.post(
            f"{_BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
            json={
                "clientcode": self._settings.angel_client_code,
                "password": self._settings.angel_pin,
                "totp": totp,
            },
            headers=self._base_headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"angelone login failed: {body.get('message')}")
        d = body["data"]
        self._jwt = d["jwtToken"]
        self._refresh_token = d["refreshToken"]
        self._feed_token = d["feedToken"]
        self._expires_at = datetime.now(UTC) + timedelta(hours=23)
        logger.info("angelone_login_ok", client=self._settings.angel_client_code)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _do_refresh(self) -> None:
        client = await self._client_get()
        resp = await client.post(
            f"{_BASE}/rest/auth/angelbroking/jwt/v1/generateTokens",
            json={"refreshToken": self._refresh_token},
            headers=self._base_headers(),
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"angelone token refresh failed: {body.get('message')}")
        d = body["data"]
        self._jwt = d["jwtToken"]
        self._refresh_token = d.get("refreshToken", self._refresh_token)
        self._expires_at = datetime.now(UTC) + timedelta(hours=23)
        logger.info("angelone_token_refreshed")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def ensure_active(self) -> None:
        async with self._lock:
            if self._jwt is None:
                await self._do_login()
            elif self._expires_at and datetime.now(UTC) >= self._expires_at - timedelta(minutes=10):
                try:
                    await self._do_refresh()
                except Exception as exc:
                    logger.warning("angelone_refresh_fell_back_to_login", error=str(exc))
                    await self._do_login()

    async def get_jwt(self) -> str:
        await self.ensure_active()
        return self._jwt  # type: ignore[return-value]

    async def get_feed_token(self) -> str:
        await self.ensure_active()
        return self._feed_token  # type: ignore[return-value]

    async def get_headers(self) -> dict[str, str]:
        await self.ensure_active()
        return self._auth_headers()

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


ANGEL_SESSION = AngelOneSession()
