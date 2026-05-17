from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class CorrelationPair(BaseModel):
    asset_a: str
    asset_b: str
    pearson: float
    spearman: float
    window_days: int
    computed_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.computed_at:
            self.computed_at = datetime.now(timezone.utc).isoformat()


class RegimeState(BaseModel):
    regime: str  # trending_up / trending_down / mean_reverting / crash / low_liquidity
    probability: float
    volatility_regime: str  # low / normal / high / extreme
    india_vix: float = 0.0
    vix: float = 0.0
    detected_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


class ArbOpportunity(BaseModel):
    type: str  # cash_futures / nse_bse / mcx_comex / crypto_exchange
    asset: str
    leg_a: str
    leg_b: str
    spread_pct: float
    direction: str  # long_a_short_b / long_b_short_a
    confidence: float
    detected_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()
