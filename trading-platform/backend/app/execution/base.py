"""BaseExecutionAdapter — Law 2 + Law 3.

Every broker/venue is a plugin that:
1. Inherits this interface
2. Sets adapter_id (used for auto-discovery and routing)
3. Receives only OrderRequest, returns only ExecutionFill — no leakage up

Layer contract: execution ONLY receives OrderRequest from the engine layer
and ONLY returns ExecutionFill. It never imports from strategies, ingestion,
or the intelligence layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.types import ExecutionFill, OrderRequest


class BaseExecutionAdapter(ABC):
    """Base class for all execution adapter plugins."""

    adapter_id: str = ""  # set on every subclass; used by plugin loader

    @abstractmethod
    async def execute(self, order: OrderRequest) -> ExecutionFill:
        """Submit an order and return the fill result."""
        ...
