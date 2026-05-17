from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.state import STATE
from app.core.types import Signal
from app.engine.service import ENGINE

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderIn(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    strategy_name: str = "manual"
    mode: str = "paper"


class OrderOut(BaseModel):
    order_id: str
    status: str
    reason: str | None = None
    filled_qty: float | None = None
    avg_price: float | None = None


@router.get("/")
async def list_orders() -> list[dict[str, str]]:
    return [{"order_id": key, "status": value} for key, value in STATE.order_status.items()]


@router.post("/", response_model=OrderOut)
async def create_order(payload: OrderIn) -> OrderOut:
    side = "buy" if payload.side.lower() == "buy" else "sell"
    signal = Signal(
        strategy_name=payload.strategy_name,
        symbol=payload.symbol,
        side=side,
        strength=1.0,
        confidence=1.0,
        ts=datetime.now(timezone.utc),
    )
    result = await ENGINE.submit_aggregated_signal(payload.symbol, [signal], payload.price, mode=payload.mode)
    status = str(result.get("status", "rejected"))
    order_id = f"{payload.symbol}-{len(STATE.orders)}"
    return OrderOut(
        order_id=order_id,
        status=status,
        reason=result.get("reason") if isinstance(result.get("reason"), str) else None,
        filled_qty=float(result["filled_qty"]) if "filled_qty" in result else None,
        avg_price=float(result["avg_price"]) if "avg_price" in result else None,
    )

