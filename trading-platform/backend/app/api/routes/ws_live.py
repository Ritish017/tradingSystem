from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.state import STATE

router = APIRouter(tags=["ws"])


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "daily_pnl": STATE.daily_realized_pnl,
                "positions": len(STATE.positions),
                "orders": len(STATE.order_status),
                "halted": STATE.trading_halted,
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return

