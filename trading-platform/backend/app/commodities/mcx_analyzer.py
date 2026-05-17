from __future__ import annotations

import structlog
from app.commodities.models import MCXContract

logger = structlog.get_logger(__name__)

_MOCK_MCX = [
    {"symbol": "GOLD", "price": 73500.0, "change_pct": 0.42, "open_interest": 45230, "oi_change_pct": 2.1, "volume": 12400, "expiry": "2025-06-05"},
    {"symbol": "SILVER", "price": 87000.0, "change_pct": 0.85, "open_interest": 28100, "oi_change_pct": 3.5, "volume": 8900, "expiry": "2025-06-05"},
    {"symbol": "CRUDEOIL", "price": 6850.0, "change_pct": -0.30, "open_interest": 62000, "oi_change_pct": -1.2, "volume": 31000, "expiry": "2025-05-19"},
    {"symbol": "COPPER", "price": 845.0, "change_pct": 0.15, "open_interest": 18500, "oi_change_pct": 0.8, "volume": 5600, "expiry": "2025-05-30"},
    {"symbol": "NATURALGAS", "price": 195.0, "change_pct": -1.20, "open_interest": 9800, "oi_change_pct": -2.5, "volume": 4200, "expiry": "2025-05-26"},
]


async def get_mcx_contracts() -> list[MCXContract]:
    """Return MCX contract data. In production: fetch from MCX API or OpenAlgo."""
    try:
        return [MCXContract(**c) for c in _MOCK_MCX]
    except Exception as exc:
        logger.error("mcx_contracts_error", error=str(exc))
        return []
