from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@lru_cache(maxsize=1)
def load_risk_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    path = root / "configs" / "features" / "default.yml"
    if not path.exists():
        return {
            "max_daily_loss_pct": 0.02,
            "max_position_concentration_pct": 0.20,
            "max_gross_exposure_pct": 1.0,
            "max_fo_margin_utilisation_pct": 0.60,
            "circuit_breaker_losses": 3,
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    risk = data.get("risk", {})
    return {
        "max_daily_loss_pct": float(risk.get("max_daily_loss_pct", 0.02)),
        "max_position_concentration_pct": float(risk.get("max_position_concentration_pct", 0.20)),
        "max_gross_exposure_pct": float(risk.get("max_gross_exposure_pct", 1.0)),
        "max_fo_margin_utilisation_pct": float(risk.get("max_fo_margin_utilisation_pct", 0.60)),
        "circuit_breaker_losses": int(risk.get("circuit_breaker_losses", 3)),
    }

