from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel


class GoldSilverSnapshot(BaseModel):
    gold_mcx_per10g: float = 0.0
    gold_comex_usd_oz: float = 0.0
    gold_lbma_usd_oz: float = 0.0
    silver_mcx_per_kg: float = 0.0
    silver_comex_usd_oz: float = 0.0
    usd_inr: float = 83.5
    gold_mcx_fair_value: float = 0.0
    gold_premium_pct: float = 0.0
    silver_premium_pct: float = 0.0
    dxy: float = 104.0
    us_real_yield_10y: float = 2.0
    central_bank_buying: bool = False
    geopolitical_risk_score: float = 0.5
    inflation_hedge_score: float = 0.5
    ai_sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    ai_confidence: float = 0.5
    updated_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()
        # Compute fair value
        if self.gold_comex_usd_oz and self.usd_inr:
            self.gold_mcx_fair_value = round((self.gold_comex_usd_oz * self.usd_inr / 31.1035) * 10, 0)
        if self.gold_mcx_fair_value and self.gold_mcx_per10g:
            self.gold_premium_pct = round(
                (self.gold_mcx_per10g - self.gold_mcx_fair_value) / self.gold_mcx_fair_value, 4
            )


class MCXContract(BaseModel):
    symbol: str
    price: float
    change_pct: float = 0.0
    open_interest: int = 0
    oi_change_pct: float = 0.0
    volume: int = 0
    expiry: str = ""
    updated_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc).isoformat()
