from __future__ import annotations

import structlog
from app.commodities.models import GoldSilverSnapshot

logger = structlog.get_logger(__name__)

# Placeholder prices — in production these come from MCX API / CCXT / data vendors
_MOCK_DATA = {
    "gold_mcx_per10g": 73500.0,
    "gold_comex_usd_oz": 2340.0,
    "gold_lbma_usd_oz": 2338.0,
    "silver_mcx_per_kg": 87000.0,
    "silver_comex_usd_oz": 29.5,
    "usd_inr": 83.6,
    "dxy": 104.2,
    "us_real_yield_10y": 2.1,
    "central_bank_buying": True,
    "geopolitical_risk_score": 0.65,
}


def _compute_inflation_hedge_score(real_yield: float, cpi: float = 5.0) -> float:
    """Higher when real yields are low and inflation is high."""
    score = 0.5
    if real_yield < 0:
        score += 0.3
    elif real_yield < 1.0:
        score += 0.15
    elif real_yield > 3.0:
        score -= 0.2
    if cpi > 6.0:
        score += 0.15
    return max(0.0, min(1.0, score))


async def get_gold_silver_snapshot() -> GoldSilverSnapshot:
    """Return current gold/silver intelligence snapshot."""
    try:
        # In production: fetch from MCX API, CCXT for COMEX, forex API for USDINR
        data = dict(_MOCK_DATA)
        inflation_hedge = _compute_inflation_hedge_score(data["us_real_yield_10y"])

        snapshot = GoldSilverSnapshot(
            **data,
            inflation_hedge_score=round(inflation_hedge, 3),
        )

        # AI sentiment from commodity analyst heuristic
        if data["us_real_yield_10y"] < 1.0 and data["central_bank_buying"]:
            snapshot.ai_sentiment = "bullish"
            snapshot.ai_confidence = 0.75
        elif data["us_real_yield_10y"] > 3.0 and data["dxy"] > 106:
            snapshot.ai_sentiment = "bearish"
            snapshot.ai_confidence = 0.65
        else:
            snapshot.ai_sentiment = "neutral"
            snapshot.ai_confidence = 0.5

        return snapshot
    except Exception as exc:
        logger.error("gold_silver_snapshot_error", error=str(exc))
        return GoldSilverSnapshot()
