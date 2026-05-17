from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.state import STATE

router = APIRouter(prefix="/pnl", tags=["pnl"])


class PnlOut(BaseModel):
    daily: float
    total_realized: float
    unrealized: float


@router.get("/", response_model=PnlOut)
async def get_pnl() -> PnlOut:
    unrealized = sum(item.unrealized_pnl for item in STATE.positions.values())
    total_realized = sum(
        (fill.filled_qty * fill.avg_price * (-1 if fill.side == "buy" else 1)) - fill.fee
        for fill in STATE.fills
    )
    return PnlOut(daily=STATE.daily_realized_pnl, total_realized=total_realized, unrealized=unrealized)

