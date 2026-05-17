from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.services.options.greeks import OptionType, compute_greeks
from app.services.options.iv import implied_volatility

_RISK_FREE_RATE = 0.065  # 6.5% RBI repo rate


def _days_to_expiry(expiry_str: str) -> float:
    """Parse Angel One expiry string (DDMMMYYYY) → years remaining."""
    for fmt in ("%d%b%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            expiry = datetime.strptime(expiry_str.upper(), fmt).replace(tzinfo=UTC)
            now = datetime.now(UTC)
            days = (expiry - now).days
            return max(days, 0) / 365.0
        except ValueError:
            continue
    return 0.0


def _enrich_strike(
    strike_data: dict[str, Any],
    S: float,
    T: float,
    option_type: OptionType,
) -> dict[str, Any]:
    """Add IV + Greeks to a single strike row."""
    strike_data = dict(strike_data)
    ltp = float(strike_data.get("ltp", 0) or 0)
    strike = float(strike_data.get("strikePrice", 0) or 0)

    iv = implied_volatility(ltp, S, strike, T, _RISK_FREE_RATE, option_type)
    if iv is not None:
        greeks = compute_greeks(S, strike, T, _RISK_FREE_RATE, iv, option_type)
        strike_data["iv"] = round(iv * 100, 2)
        strike_data.update(greeks)
    else:
        strike_data["iv"] = None

    return strike_data


def enrich_chain_with_greeks(chain_data: dict[str, Any]) -> dict[str, Any]:
    """
    Takes Angel One optionChain response `data` dict and adds IV + Greeks
    to each CE/PE row.

    Expected structure:
      {"fetched": [{"strikePrice": ..., "CE": {...}, "PE": {...}}, ...]}
    """
    spot_price = float(chain_data.get("underlyingLtpValue", 0) or 0)
    expiry_date = str(chain_data.get("expiryDate", "") or "")
    T = _days_to_expiry(expiry_date)

    fetched = chain_data.get("fetched", [])
    enriched = []
    for row in fetched:
        row = dict(row)
        if "CE" in row and isinstance(row["CE"], dict):
            row["CE"] = _enrich_strike(row["CE"], spot_price, T, "CE")
        if "PE" in row and isinstance(row["PE"], dict):
            row["PE"] = _enrich_strike(row["PE"], spot_price, T, "PE")
        enriched.append(row)

    return {**chain_data, "fetched": enriched}
