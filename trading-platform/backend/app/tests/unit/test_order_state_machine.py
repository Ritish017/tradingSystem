from __future__ import annotations

import pytest

from app.core.state import STATE
from app.core.types import OrderRequest
from app.execution.paper import PaperExecutionAdapter


@pytest.mark.asyncio
async def test_order_transitions_to_filled_or_partial() -> None:
    adapter = PaperExecutionAdapter()
    order = OrderRequest(client_order_id="order-1", symbol="BTCUSDT", side="buy", quantity=20, price=100)
    STATE.order_status[order.client_order_id] = "pending"
    STATE.order_status[order.client_order_id] = "submitted"
    fill = await adapter.execute(order)
    assert fill.status in {"filled", "partial"}
    assert STATE.order_status[order.client_order_id] == fill.status

