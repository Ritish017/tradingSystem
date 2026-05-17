from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.types import ExecutionFill, OrderRequest
from app.execution.base import BaseExecutionAdapter


class IndiaOpenAlgoAdapter(BaseExecutionAdapter):
    adapter_id = "india"

    def __init__(self) -> None:
        settings = get_settings()
        self._base = str(settings.openalgo_base_url).rstrip("/")

    async def execute(self, order: OrderRequest) -> ExecutionFill:
        payload = {
            "symbol": order.symbol,
            "side": order.side.upper(),
            "quantity": order.quantity,
            "order_type": order.order_type.upper(),
            "price": order.price,
            "client_order_id": order.client_order_id,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            # OpenAlgo contract differs per broker profile; keep generic payload.
            await client.post(f"{self._base}/api/v1/orders", json=payload)
        return ExecutionFill(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            avg_price=order.price,
            status="submitted",
            fee=0.0,
            slippage_bps=0.0,
        )

