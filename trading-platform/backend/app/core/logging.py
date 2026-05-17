"""Structured logging with trace ID propagation — Law 7.

Every event that flows through the system carries a trace_id.
Every layer logs what it received, what it decided, what it emitted.

Usage:
    from app.core.logging import get_logger, bind_trace_id, clear_trace_id

    logger = get_logger(__name__)

    bind_trace_id(event.get("_trace_id"))
    logger.info("signal_received", symbol="RELIANCE", side="buy")
    clear_trace_id()
"""
from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

try:
    import structlog
    _HAS_STRUCTLOG = True
except ModuleNotFoundError:
    _HAS_STRUCTLOG = False
    structlog = None  # type: ignore[assignment]


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    if not _HAS_STRUCTLOG:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_trace_id(trace_id: str | None = None) -> str:
    """Bind a trace_id to the current async context so all subsequent
    log lines in this context automatically carry it.
    Returns the trace_id (generated if not supplied).
    """
    tid = trace_id or str(uuid.uuid4())
    if _HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(trace_id=tid)
    return tid


def clear_trace_id() -> None:
    """Clear trace context at the end of a request/event processing cycle."""
    if _HAS_STRUCTLOG:
        structlog.contextvars.unbind_contextvars("trace_id")


class _FallbackLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info("%s %s", event, kwargs if kwargs else "")

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning("%s %s", event, kwargs if kwargs else "")

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error("%s %s", event, kwargs if kwargs else "")

    def debug(self, event: str, **kwargs: Any) -> None:
        self._logger.debug("%s %s", event, kwargs if kwargs else "")


def get_logger(name: str) -> Any:
    if not _HAS_STRUCTLOG:
        return _FallbackLogger(name)
    return structlog.get_logger(name)
