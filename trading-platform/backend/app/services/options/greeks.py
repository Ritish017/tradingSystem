from __future__ import annotations

import math
from typing import Literal

OptionType = Literal["CE", "PE"]

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def black_scholes_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
) -> float:
    """Black-Scholes option price. T in years, r and sigma as decimals."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0.0) if option_type == "CE" else max(K - S, 0.0)
        return intrinsic
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    if option_type == "CE":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def compute_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
) -> dict[str, float]:
    """Returns delta, gamma, theta, vega, rho."""
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    nd1 = _norm_pdf(d1)
    disc = math.exp(-r * T)

    gamma = nd1 / (S * sigma * sqrt_T)
    vega = S * nd1 * sqrt_T / 100.0  # per 1% move in vol

    if option_type == "CE":
        delta = _norm_cdf(d1)
        theta = (
            -(S * nd1 * sigma) / (2 * sqrt_T) - r * K * disc * _norm_cdf(d2)
        ) / 365.0
        rho = K * T * disc * _norm_cdf(d2) / 100.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(S * nd1 * sigma) / (2 * sqrt_T) + r * K * disc * _norm_cdf(-d2)
        ) / 365.0
        rho = -K * T * disc * _norm_cdf(-d2) / 100.0

    return {
        "delta": round(delta, 6),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
    }
