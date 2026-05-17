from __future__ import annotations

from typing import Any


def build_oi_heatmap(chain_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build OI heatmap data: strikes × {call_oi, put_oi, call_oi_change, put_oi_change}.
    Sorted by strike descending (highest strike first for standard chain view).
    """
    rows = []
    max_call_oi = 0.0
    max_put_oi = 0.0

    for row in chain_rows:
        strike = float(row.get("strikePrice", 0) or 0)
        if strike <= 0:
            continue
        ce = row.get("CE") or {}
        pe = row.get("PE") or {}
        call_oi = float(ce.get("openInterest", 0) or 0)
        put_oi = float(pe.get("openInterest", 0) or 0)
        call_oi_chg = float(ce.get("changeinOpenInterest", 0) or 0)
        put_oi_chg = float(pe.get("changeinOpenInterest", 0) or 0)
        call_ltp = float(ce.get("ltp", 0) or 0)
        put_ltp = float(pe.get("ltp", 0) or 0)
        call_iv = ce.get("iv")
        put_iv = pe.get("iv")

        max_call_oi = max(max_call_oi, call_oi)
        max_put_oi = max(max_put_oi, put_oi)

        rows.append(
            {
                "strike": strike,
                "call_oi": call_oi,
                "put_oi": put_oi,
                "call_oi_change": call_oi_chg,
                "put_oi_change": put_oi_chg,
                "call_ltp": call_ltp,
                "put_ltp": put_ltp,
                "call_iv": call_iv,
                "put_iv": put_iv,
                # normalised 0-1 for heat intensity
                "call_heat": call_oi / max_call_oi if max_call_oi > 0 else 0.0,
                "put_heat": put_oi / max_put_oi if max_put_oi > 0 else 0.0,
            }
        )

    # Re-normalise after collecting max values
    for r in rows:
        r["call_heat"] = round(r["call_oi"] / max_call_oi, 4) if max_call_oi > 0 else 0.0
        r["put_heat"] = round(r["put_oi"] / max_put_oi, 4) if max_put_oi > 0 else 0.0

    rows.sort(key=lambda x: x["strike"], reverse=True)
    return {
        "rows": rows,
        "max_call_oi": max_call_oi,
        "max_put_oi": max_put_oi,
    }
