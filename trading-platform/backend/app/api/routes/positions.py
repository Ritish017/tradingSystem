from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.state import STATE

router = APIRouter(prefix="/positions", tags=["positions"])


class PositionOut(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    unrealized_pnl: float


@router.get("/", response_model=list[PositionOut])
async def list_positions() -> list[PositionOut]:
    return [
        PositionOut(
            symbol=item.symbol,
            quantity=item.quantity,
            avg_price=item.avg_price,
            unrealized_pnl=item.unrealized_pnl,
        )
        for item in STATE.positions.values()
    ]

