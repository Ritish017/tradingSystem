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

OrderCallback = Callable[[dict[str, Any]], Awaitable[None]]


class AngelOneOrderStream:
    """
    Wraps SmartWebSocketOrderUpdate — streams live order status events.
    Bridges thread callbacks → asyncio queue.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=5_000)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None
        self._ws_obj: Any = None
        self._running = False
        self._callbacks: list[OrderCallback] = []

    def add_callback(self, cb: OrderCallback) -> None:
        self._callbacks.append(cb)

    def _on_message(self, wsapp: Any, message: Any) -> None:
        if self._loop is None:
            return
        try:
            data = json.loads(message) if isinstance(message, str) else message
        except Exception:
            return
        asyncio.run_coroutine_threadsafe(self._enqueue(data), self._loop)

    async def _enqueue(self, message: dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self._queue.put_nowait(message)

    def _on_open(self, wsapp: Any) -> None:
        logger.info("angelone_order_stream_connected")

    def _on_error(self, wsapp: Any, error: Any) -> None:
        logger.error("angelone_order_stream_error", error=str(error))

    def _on_close(self, wsapp: Any) -> None:
        logger.info("angelone_order_stream_closed")
        self._running = False

    async def start(self) -> None:
        try:
            from SmartApi.SmartWebSocketOrderUpdate import SmartWebSocketOrderUpdate  # type: ignore[import]
        except ImportError:
            logger.error("smartapi_python_not_installed_for_order_stream")
            return

        jwt = await ANGEL_SESSION.get_jwt()
        self._loop = asyncio.get_running_loop()
        self._running = True

        ws = SmartWebSocketOrderUpdate(
            client_code=self._settings.angel_client_code,
            auth_token=jwt,
        )
        ws.on_message = self._on_message
        ws.on_open = self._on_open
        ws.on_error = self._on_error
        ws.on_close = self._on_close
        self._ws_obj = ws

        self._ws_thread = threading.Thread(
            target=ws.run_forever, daemon=True, name="angel-order-ws"
        )
        self._ws_thread.start()
        logger.info("angelone_order_stream_thread_started")

        # start draining queue into registered callbacks
        asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                for cb in self._callbacks:
                    try:
                        await cb(event)
                    except Exception as exc:
                        logger.error("angelone_order_callback_error", error=str(exc))
            except asyncio.TimeoutError:
                continue

    async def stream(self) -> Any:
        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        self._running = False
        if self._ws_obj is not None:
            try:
                self._ws_obj.close()
            except Exception:
                pass


ANGEL_ORDER_STREAM = AngelOneOrderStream()
