from __future__ import annotations

from random import uniform

from app.core.state import STATE
from app.core.types import ExecutionFill, OrderRequest
from app.execution.base import BaseExecutionAdapter


class PaperExecutionAdapter(BaseExecutionAdapter):
    adapter_id = "paper"

    async def execute(self, order: OrderRequest) -> ExecutionFill:
        slippage_bps = uniform(1.0, 8.0)
        fill_ratio = 1.0 if order.quantity <= 10 else 0.6
        filled_qty = round(order.quantity * fill_ratio, 8)
        slip_multiplier = 1 + (slippage_bps / 10_000) if order.side == "buy" else 1 - (slippage_bps / 10_000)
        avg_price = order.price * slip_multiplier
        fee = abs(filled_qty * avg_price) * 0.0005
        status = "filled" if fill_ratio >= 1 else "partial"
        fill = ExecutionFill(
            order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            requested_qty=order.quantity,
            filled_qty=filled_qty,
            avg_price=avg_price,
            status=status,
            fee=fee,
            slippage_bps=slippage_bps,
        )
        STATE.fills.append(fill)
        STATE.order_status[order.client_order_id] = status
        return fill

