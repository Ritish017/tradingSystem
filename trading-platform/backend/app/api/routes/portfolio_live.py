from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.angelone.portfolio import PORTFOLIO

router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


@router.get("/holdings")
async def get_holdings() -> list[dict[str, Any]]:
    try:
        return await PORTFOLIO.get_holdings_with_ltp()
    except Exception as exc:
        raise HTTPException(502, f"Holdings fetch failed: {exc}") from exc


@router.get("/positions")
async def get_live_positions() -> list[dict[str, Any]]:
    try:
        return await PORTFOLIO.get_positions()
    except Exception as exc:
        raise HTTPException(502, f"Positions fetch failed: {exc}") from exc


@router.get("/pnl")
async def get_live_pnl() -> dict[str, Any]:
    try:
        pnl = await PORTFOLIO.compute_pnl()
        funds = await PORTFOLIO.get_funds()
        return {
            **pnl,
            "available_cash": float(funds.get("availablecash", 0) or 0),
            "used_margin": float(funds.get("utilisedMargin", 0) or 0),
            "net": float(funds.get("net", 0) or 0),
        }
    except Exception as exc:
        raise HTTPException(502, f"PnL fetch failed: {exc}") from exc


@router.get("/funds")
async def get_funds() -> dict[str, Any]:
    try:
        return await PORTFOLIO.get_funds()
    except Exception as exc:
        raise HTTPException(502, f"Funds fetch failed: {exc}") from exc
