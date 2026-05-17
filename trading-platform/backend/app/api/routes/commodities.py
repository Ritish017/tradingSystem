from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.commodities.gold_silver_tracker import get_gold_silver_snapshot
from app.commodities.mcx_analyzer import get_mcx_contracts

router = APIRouter(prefix="/commodities", tags=["commodities"])


@router.get("/gold-silver")
async def get_gold_silver() -> dict[str, Any]:
    """Gold & Silver intelligence dashboard data."""
    snapshot = await get_gold_silver_snapshot()
    return snapshot.model_dump()


@router.get("/mcx")
async def get_mcx() -> list[dict[str, Any]]:
    """MCX contract data."""
    contracts = await get_mcx_contracts()
    return [c.model_dump() for c in contracts]


@router.get("/spread")
async def get_spread() -> dict[str, Any]:
    """India vs global commodity spreads."""
    snapshot = await get_gold_silver_snapshot()
    return {
        "gold_mcx_vs_comex_premium_pct": snapshot.gold_premium_pct,
        "gold_mcx_fair_value": snapshot.gold_mcx_fair_value,
        "gold_mcx_actual": snapshot.gold_mcx_per10g,
        "silver_mcx_per_kg": snapshot.silver_mcx_per_kg,
        "usd_inr": snapshot.usd_inr,
    }
