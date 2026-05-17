from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.angelone.options import OPTION_CHAIN
from app.services.options.chain import enrich_chain_with_greeks
from app.services.options.heatmap import build_oi_heatmap
from app.services.options.maxpain import compute_max_pain
from app.services.options.pcr import compute_pcr
from app.services.options.greeks import compute_greeks

router = APIRouter(prefix="/v1/options", tags=["options"])


@router.get("/chain")
async def get_option_chain(
    symbol: str = Query(..., description="Underlying e.g. NIFTY, BANKNIFTY, RELIANCE"),
    expiry: str = Query(..., description="Expiry date DDMMMYYYY e.g. 25JAN2024"),
    strike: float = Query(0.0, description="Filter to single strike (0 = full chain)"),
) -> dict[str, Any]:
    try:
        chain = await OPTION_CHAIN.get_option_chain(symbol, expiry, strike, enrich_greeks=True)
        rows = chain.get("fetched", [])
        pcr = compute_pcr(rows)
        max_pain = compute_max_pain(rows)
        heatmap = build_oi_heatmap(rows)
        return {
            "symbol": symbol,
            "expiry": expiry,
            "spot": chain.get("underlyingLtpValue", 0),
            "pcr": pcr,
            "max_pain": max_pain,
            "heatmap": heatmap,
            "chain": rows,
        }
    except Exception as exc:
        raise HTTPException(502, f"Option chain fetch failed: {exc}") from exc


@router.get("/greeks")
async def get_greeks(
    spot: float = Query(..., description="Underlying spot price"),
    strike: float = Query(..., description="Strike price"),
    expiry_days: float = Query(..., description="Days to expiry"),
    iv: float = Query(..., description="Implied volatility as decimal e.g. 0.18 = 18%%"),
    option_type: str = Query("CE", description="CE or PE"),
    rate: float = Query(0.065, description="Risk-free rate as decimal"),
) -> dict[str, Any]:
    T = expiry_days / 365.0
    ot = "CE" if option_type.upper() == "CE" else "PE"
    greeks = compute_greeks(spot, strike, T, rate, iv, ot)  # type: ignore[arg-type]
    return {"greeks": greeks, "inputs": {"spot": spot, "strike": strike, "expiry_days": expiry_days, "iv": iv, "option_type": ot}}


@router.get("/expiries")
async def get_expiries(
    symbol: str = Query(...),
    exchange: str = Query("NFO"),
) -> list[str]:
    try:
        return await OPTION_CHAIN.get_expiry_list(symbol, exchange)
    except Exception as exc:
        raise HTTPException(502, f"Expiry list failed: {exc}") from exc


@router.get("/pcr")
async def get_pcr(
    symbol: str = Query(...),
    expiry: str = Query(...),
) -> dict[str, Any]:
    try:
        chain = await OPTION_CHAIN.get_option_chain(symbol, expiry, enrich_greeks=False)
        rows = chain.get("fetched", [])
        return compute_pcr(rows)
    except Exception as exc:
        raise HTTPException(502, f"PCR compute failed: {exc}") from exc


@router.get("/maxpain")
async def get_max_pain(
    symbol: str = Query(...),
    expiry: str = Query(...),
) -> dict[str, Any]:
    try:
        chain = await OPTION_CHAIN.get_option_chain(symbol, expiry, enrich_greeks=False)
        rows = chain.get("fetched", [])
        return compute_max_pain(rows)
    except Exception as exc:
        raise HTTPException(502, f"Max pain compute failed: {exc}") from exc


@router.get("/heatmap")
async def get_heatmap(
    symbol: str = Query(...),
    expiry: str = Query(...),
) -> dict[str, Any]:
    try:
        chain = await OPTION_CHAIN.get_option_chain(symbol, expiry, enrich_greeks=False)
        rows = chain.get("fetched", [])
        return build_oi_heatmap(rows)
    except Exception as exc:
        raise HTTPException(502, f"Heatmap build failed: {exc}") from exc
