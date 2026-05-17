from __future__ import annotations

from typing import Any


def compute_max_pain(chain_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Max Pain = strike at which total option writers' loss is minimised.
    For each possible expiry price (= each strike), compute sum of
    (intrinsic value × OI) across all call and put OI.
    """
    strikes: list[float] = []
    call_oi: dict[float, float] = {}
    put_oi: dict[float, float] = {}

    for row in chain_rows:
        strike = float(row.get("strikePrice", 0) or 0)
        if strike <= 0:
            continue
        strikes.append(strike)
        call_oi[strike] = float((row.get("CE") or {}).get("openInterest", 0) or 0)
        put_oi[strike] = float((row.get("PE") or {}).get("openInterest", 0) or 0)

    if not strikes:
        return {"max_pain_strike": 0.0, "pain_values": []}

    all_strikes = sorted(set(strikes))
    pain_values: list[dict[str, float]] = []
    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for test_price in all_strikes:
        total_pain = 0.0
        for k in all_strikes:
            # call holders' pain at expiry test_price
            total_pain += max(test_price - k, 0.0) * call_oi.get(k, 0.0)
            # put holders' pain at expiry test_price
            total_pain += max(k - test_price, 0.0) * put_oi.get(k, 0.0)
        pain_values.append({"strike": test_price, "pain": total_pain})
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_price

    return {
        "max_pain_strike": max_pain_strike,
        "min_total_pain": min_pain,
        "pain_values": pain_values,
    }
