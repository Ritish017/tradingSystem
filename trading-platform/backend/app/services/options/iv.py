from __future__ import annotations

import math
from typing import Literal

from app.services.options.greeks import OptionType, black_scholes_price

_MAX_ITER = 200
_TOL = 1e-6
_SIGMA_LOW = 1e-4
_SIGMA_HIGH = 20.0  # 2000% vol cap


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
) -> float | None:
    """
    Brentq bisection method for IV. Returns None when no solution exists.
    """
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None

    def objective(sigma: float) -> float:
        return black_scholes_price(S, K, T, r, sigma, option_type) - market_price

    f_low = objective(_SIGMA_LOW)
    f_high = objective(_SIGMA_HIGH)

    # Check if solution exists in bracket
    if f_low * f_high > 0:
        return None

    a, b = _SIGMA_LOW, _SIGMA_HIGH
    fa, fb = f_low, f_high

    for _ in range(_MAX_ITER):
        midpoint = (a + b) / 2.0
        fm = objective(midpoint)
        if abs(fm) < _TOL or (b - a) / 2.0 < _TOL:
            return round(midpoint, 6)
        if fa * fm < 0:
            b, fb = midpoint, fm
        else:
            a, fa = midpoint, fm

    return None


def iv_to_percent(iv: float | None) -> float:
    """Convert decimal IV to percentage."""
    return round((iv or 0.0) * 100.0, 2)
