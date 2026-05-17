"""Plugin-based Order Router — Law 1 + Law 3.

Before (violation): hardcoded imports of all 4 adapter classes.
After: reads adapters from REGISTRY at call time. Adding a new broker
requires zero changes here — only a new adapter file + adapter_id.

Layer contract: receives OrderRequest, returns ExecutionFill.
Never imports from ingestion, strategies, or intelligence layers.
"""
from __future__ import annotations

from app.core.logging import get_logger, bind_trace_id
from app.core.types import ExecutionFill, OrderRequest
from app.plugins.registry import REGISTRY

logger = get_logger(__name__)


class OrderRouter:
    """Routes an OrderRequest to the correct execution adapter via the plugin registry.

    adapter_id is determined by the order's strategy context or caller-supplied mode.
    """

    async def route(self, order: OrderRequest, mode: str = "paper") -> ExecutionFill:
        bind_trace_id(order.trace_id)
        logger.info(
            "order_router_received",
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            qty=order.quantity,
            mode=mode,
            trace_id=order.trace_id,
        )

        adapter_cls = REGISTRY.get_adapter(mode)
        if adapter_cls is None:
            logger.error(
                "order_router_no_adapter",
                mode=mode,
                registered=list(REGISTRY.list_adapters().keys()),
                trace_id=order.trace_id,
            )
            # Graceful degradation: fall back to paper adapter
            adapter_cls = REGISTRY.get_adapter("paper")
            if adapter_cls is None:
                raise RuntimeError(
                    f"No execution adapter found for mode='{mode}' and paper fallback not registered"
                )
            logger.warning("order_router_fell_back_to_paper", original_mode=mode)

        adapter = adapter_cls()
        fill = await adapter.execute(order)

        logger.info(
            "order_router_fill",
            order_id=fill.order_id,
            status=fill.status,
            filled_qty=fill.filled_qty,
            avg_price=fill.avg_price,
            trace_id=fill.trace_id,
        )
        return fill
