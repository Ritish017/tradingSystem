"""Macro Data Service

Fetches every 60s:
- DXY (USD Index)
- US 10Y Bond Yield
- VIX
- S&P 500 change %
- Nifty 50 change %
- Gold USD spot

Publishes to: macro_data
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.bus.event_bus import BUS
from app.bus.topics import MACRO_DATA
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_POLL_INTERVAL = 60

_MACRO_TICKERS = {
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "vix": "^VIX",
    "sp500": "^GSPC",
    "nifty": "^NSEI",
    "gold_usd": "GC=F",
}

_prev_prices: dict[str, float] = {}


def _pct_change(symbol: str, price: float) -> float:
    prev = _prev_prices.get(symbol)
    _prev_prices[symbol] = price
    if prev is None or prev == 0:
        return 0.0
    return round((price - prev) / prev * 100, 4)


async def _fetch_macro() -> dict[str, Any] | None:
    try:
        import yfinance as yf
        tickers_str = " ".join(_MACRO_TICKERS.values())
        tickers = yf.Tickers(tickers_str)
        result: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat(), "source": "macro"}

        for field, sym in _MACRO_TICKERS.items():
            try:
                info = tickers.tickers[sym].fast_info
                price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                if price is not None:
                    price = float(price)
                    if field in ("sp500", "nifty"):
                        result[f"{field}_change_pct"] = _pct_change(field, price)
                    else:
                        result[field] = price
            except Exception as exc:
                logger.warning("macro_ticker_error", field=field, symbol=sym, error=str(exc))

        return result if len(result) > 2 else None
    except ImportError:
        logger.warning("yfinance_not_installed")
        return None


async def run() -> None:
    logger.info("macro_data_service_started")
    while True:
        try:
            macro = await _fetch_macro()
            if macro:
                await BUS.publish(MACRO_DATA, macro)
                logger.info("macro_published", fields=list(macro.keys()))
        except Exception as exc:
            logger.error("macro_poll_error", error=str(exc))
        await asyncio.sleep(_POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
