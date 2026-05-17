from __future__ import annotations

from typing import Any


def compute_pcr(chain_rows: list[dict[str, Any]]) -> dict[str, float]:
    """
    Compute Put-Call Ratio from option chain rows.
    Returns volume-based PCR, OI-based PCR, and interpretation.
    """
    total_call_oi = 0.0
    total_put_oi = 0.0
    total_call_vol = 0.0
    total_put_vol = 0.0

    for row in chain_rows:
        ce = row.get("CE", {}) or {}
        pe = row.get("PE", {}) or {}

        total_call_oi += float(ce.get("openInterest", 0) or 0)
        total_put_oi += float(pe.get("openInterest", 0) or 0)
        total_call_vol += float(ce.get("totalBuyQuantity", 0) or 0)
        total_put_vol += float(pe.get("totalBuyQuantity", 0) or 0)

    pcr_oi = (total_put_oi / total_call_oi) if total_call_oi > 0 else 0.0
    pcr_vol = (total_put_vol / total_call_vol) if total_call_vol > 0 else 0.0

    if pcr_oi > 1.2:
        sentiment = "bullish"
    elif pcr_oi < 0.7:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "pcr_oi": round(pcr_oi, 4),
        "pcr_volume": round(pcr_vol, 4),
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
        "sentiment": sentiment,
    }
