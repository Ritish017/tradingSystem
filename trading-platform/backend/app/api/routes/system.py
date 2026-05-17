from __future__ import annotations

from fastapi import APIRouter

from app.core.state import STATE

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/halt")
async def halt() -> dict[str, str]:
    STATE.trading_halted = True
    STATE.halted_reason = "manual-kill-switch"
    return {"status": "ok", "message": "trading halted"}


@router.post("/resume")
async def resume() -> dict[str, str]:
    STATE.trading_halted = False
    STATE.halted_reason = None
    return {"status": "ok", "message": "trading resumed"}

