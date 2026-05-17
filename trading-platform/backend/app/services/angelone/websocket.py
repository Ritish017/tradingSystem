from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

TickCallback = Callable[[dict[str, Any]], Awaitable[None]]

_MODE_LTP = 1
_MODE_QUOTE = 2
_MODE_SNAP = 3

_EXCHANGE_TYPE = {
    "NSE": 1,
    "NFO": 2,
    "BSE": 3,
    "BFO": 4,
    "MCX": 5,
}


class AngelOneWebSocket:
    """
    Wraps SmartWebSocketV2 from smartapi-python.
    Bridges the threaded callback model to an asyncio queue so callers
    can simply `async for tick in ws.stream()`.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50_000)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None
        self._ws_obj: Any = None
        self._subscriptions: list[dict[str, Any]] = []
        self._running = False

    def _on_data(self, wsapp: Any, message: Any, data_type: Any, continue_flag: Any) -> None:
        if not isinstance(message, dict):
            return
        if self._loop is None:
            return
        # fire-and-forget into the asyncio queue from the ws thread
        asyncio.run_coroutine_threadsafe(
            self._enqueue(message), self._loop
        )

    async def _enqueue(self, message: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            # drop oldest
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(message)

    def _on_open(self, wsapp: Any) -> None:
        logger.info("angelone_ws_connected")
        for sub in self._subscriptions:
            try:
                wsapp.subscribe(sub["correlation_id"], sub["mode"], sub["token_list"])
                logger.info("angelone_ws_subscribed", correlation_id=sub["correlation_id"])
            except Exception as exc:
                logger.error("angelone_ws_subscribe_error", error=str(exc))

    def _on_error(self, wsapp: Any, error: Any) -> None:
        logger.error("angelone_ws_error", error=str(error))

    def _on_close(self, wsapp: Any) -> None:
        logger.info("angelone_ws_closed")
        self._running = False

    def add_subscription(
        self,
        exchange: str,
        tokens: list[str],
        mode: int = _MODE_QUOTE,
        correlation_id: str = "trading-engine",
    ) -> None:
        exchange_type = _EXCHANGE_TYPE.get(exchange.upper(), 1)
        self._subscriptions.append(
            {
                "correlation_id": correlation_id,
                "mode": mode,
                "token_list": [{"exchangeType": exchange_type, "tokens": tokens}],
            }
        )

    async def start(self) -> None:
        try:
            from SmartApi.SmartWebSocketV2 import SmartWebSocketV2  # type: ignore[import]
        except ImportError:
            logger.error("smartapi_python_not_installed")
            return

        jwt = await ANGEL_SESSION.get_jwt()
        feed_token = await ANGEL_SESSION.get_feed_token()
        self._loop = asyncio.get_running_loop()
        self._running = True

        ws = SmartWebSocketV2(
            auth_token=jwt,
            api_key=self._settings.angel_api_key,
            client_code=self._settings.angel_client_code,
            feed_token=feed_token,
        )
        ws.on_data = self._on_data
        ws.on_open = self._on_open
        ws.on_error = self._on_error
        ws.on_close = self._on_close
        self._ws_obj = ws

        self._ws_thread = threading.Thread(target=ws.connect, daemon=True, name="angel-ws")
        self._ws_thread.start()
        logger.info("angelone_ws_thread_started")

    async def stream(self) -> Any:
        while True:
            try:
                tick = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                yield tick
            except asyncio.TimeoutError:
                continue

    def subscribe(
        self,
        exchange: str,
        tokens: list[str],
        mode: int = _MODE_QUOTE,
        correlation_id: str = "dynamic",
    ) -> None:
        exchange_type = _EXCHANGE_TYPE.get(exchange.upper(), 1)
        token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
        if self._ws_obj is not None:
            try:
                self._ws_obj.subscribe(correlation_id, mode, token_list)
            except Exception as exc:
                logger.error("angelone_ws_dynamic_subscribe_error", error=str(exc))
        self._subscriptions.append(
            {"correlation_id": correlation_id, "mode": mode, "token_list": token_list}
        )

    def unsubscribe(
        self,
        exchange: str,
        tokens: list[str],
        mode: int = _MODE_QUOTE,
        correlation_id: str = "dynamic",
    ) -> None:
        exchange_type = _EXCHANGE_TYPE.get(exchange.upper(), 1)
        token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
        if self._ws_obj is not None:
            try:
                self._ws_obj.unsubscribe(correlation_id, mode, token_list)
            except Exception as exc:
                logger.error("angelone_ws_unsubscribe_error", error=str(exc))

    def stop(self) -> None:
        self._running = False
        if self._ws_obj is not None:
            try:
                self._ws_obj.close_connection()
            except Exception:
                pass


ANGEL_WS = AngelOneWebSocket()
