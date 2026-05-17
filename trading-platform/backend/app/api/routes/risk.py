from __future__ import annotations

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.state import STATE

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskSnapshot(BaseModel):
    halted: bool
    halted_reason: str | None
    daily_realized_pnl: float
    gross_exposure: float
    fo_margin_utilisation: float
    capital: float


class KillSwitchRequest(BaseModel):
    reason: str = "manual_halt"


class KillSwitchResponse(BaseModel):
    success: bool
    message: str


@router.get("/", response_model=RiskSnapshot)
async def get_risk_snapshot() -> RiskSnapshot:
    return RiskSnapshot(
        halted=STATE.trading_halted,
        halted_reason=STATE.halted_reason,
        daily_realized_pnl=STATE.daily_realized_pnl,
        gross_exposure=STATE.gross_exposure,
        fo_margin_utilisation=STATE.fo_margin_utilisation,
        capital=STATE.capital,
    )


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def activate_kill_switch(request: KillSwitchRequest) -> KillSwitchResponse:
    """Emergency kill switch - halts all trading immediately."""
    try:
        # Set Redis flag for distributed systems
        settings = get_settings()
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.set("system:halt", "true", ex=86400)  # 24h TTL
        await redis_client.close()
        
        # Set in-memory state
        STATE.trading_halted = True
        STATE.halted_reason = request.reason
        
        return KillSwitchResponse(
            success=True,
            message=f"Kill switch activated: {request.reason}"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Kill switch failed: {exc}")


@router.post("/resume", response_model=KillSwitchResponse)
async def resume_trading() -> KillSwitchResponse:
    """Resume trading after manual review."""
    try:
        settings = get_settings()
        redis_client = redis.from_url(settings.redis_url)
        await redis_client.delete("system:halt")
        await redis_client.close()
        
        STATE.trading_halted = False
        STATE.halted_reason = None
        
        return KillSwitchResponse(
            success=True,
            message="Trading resumed"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Resume failed: {exc}")

