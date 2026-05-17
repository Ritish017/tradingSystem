from __future__ import annotations

from typing import Any

from app.cross_market.models import RegimeState


def detect_regime(market_data: dict[str, Any]) -> RegimeState:
    """Classify market regime from price/volatility data."""
    india_vix = float(market_data.get("india_vix", 14.0))
    vix = float(market_data.get("vix", 15.0))
    nifty_returns_5d = float(market_data.get("nifty_returns_5d_pct", 0.0))
    nifty_returns_20d = float(market_data.get("nifty_returns_20d_pct", 0.0))
    breadth_advance_decline = float(market_data.get("advance_decline_ratio", 1.0))
    avg_volume_ratio = float(market_data.get("avg_volume_ratio", 1.0))

    # Volatility regime
    if india_vix > 30 or vix > 35:
        vol_regime = "extreme"
    elif india_vix > 22 or vix > 25:
        vol_regime = "high"
    elif india_vix < 12 or vix < 12:
        vol_regime = "low"
    else:
        vol_regime = "normal"

    # Market regime
    if vix > 35 or india_vix > 30:
        regime = "crash"
        probability = min(0.95, (vix - 25) / 30)
    elif avg_volume_ratio < 0.5:
        regime = "low_liquidity"
        probability = 0.7
    elif nifty_returns_20d > 3.0 and breadth_advance_decline > 1.5:
        regime = "trending_up"
        probability = min(0.9, 0.5 + nifty_returns_20d / 20)
    elif nifty_returns_20d < -3.0 and breadth_advance_decline < 0.7:
        regime = "trending_down"
        probability = min(0.9, 0.5 + abs(nifty_returns_20d) / 20)
    else:
        regime = "mean_reverting"
        probability = 0.6

    return RegimeState(
        regime=regime,
        probability=round(probability, 3),
        volatility_regime=vol_regime,
        india_vix=india_vix,
        vix=vix,
    )
