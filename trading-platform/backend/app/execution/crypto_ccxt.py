from __future__ import annotations

from app.core.types import ExecutionFill, OrderRequest
from app.execution.base import BaseExecutionAdapter


class CryptoExecutionAdapter(BaseExecutionAdapter):
    adapter_id = "crypto"

    async def execute(self, order: OrderRequest) -> ExecutionFill:
        # Exchange-specific validation (lot, min notional, fee currency) belongs here.
        min_notional = 5.0
        order_notional = abs(order.quantity * order.price)
        if order_notional < min_notional:
            return ExecutionFill(
                order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                requested_qty=order.quantity,
                filled_qty=0.0,
                avg_price=order.price,
                status="rejected",
                fee=0.0,
                slippage_bps=0.0,
            )
        fee = order_notional * 0.001
        return ExecutionFill(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=order.quantity,
            avg_price=order.price,
            status="filled",
            fee=fee,
            slippage_bps=2.0,
        )

