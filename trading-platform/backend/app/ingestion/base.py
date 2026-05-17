"""BaseIngester — Law 2 + Law 3.

Every data source is a plugin that:
1. Inherits this interface
2. Sets source_id (used for auto-discovery)
3. Publishes only to the event bus — never calls engine or strategy directly

Layer contract: ingestion ONLY publishes. It never imports from engine,
strategies, execution, or storage layers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseIngester(ABC):
    """Base class for all market data ingestion plugins."""

    source_id: str = ""  # set on every subclass; used by plugin loader

    @abstractmethod
    async def run(self) -> None:
        """Start the ingestion loop. Must be non-blocking (runs as asyncio task)."""
        ...

    def subscribe_symbols(self, symbols: list[str]) -> None:
        """Dynamically add symbols at runtime. Override if supported."""

    def metadata(self) -> dict[str, Any]:
        return {"source_id": self.source_id}
