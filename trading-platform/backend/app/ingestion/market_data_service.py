"""Market Data Service — Law 1 + Law 4.

Before (violations):
- Built raw dicts instead of canonical MarketTick (Law 4).
- Imported publish() directly from hybrid_engine.kafka_utils (Law 1 + Law 2).

After:
- Each tick is a MarketTick (canonical schema, normalized at the boundary).
- All publishes go through BUS (single data highway).
- trace_id auto-generated on each MarketTick.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.bus.event_bus import BUS
from app.bus.topics import MARKET_TICKS
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.types import MarketTick

logger = get_logger(__name__)
settings = get_settings()

_INDIA_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "NIFTY50.NS", "^NSEI", "^NSEBANK",
]
_CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
_COMMODITY_SYMBOLS = ["GC=F", "SI=F", "CL=F"]

_POLL_INTERVAL = 60  # seconds


def _map_symbol(raw: str) -> str:
    mapping = {
        "RELIANCE.NS": "NSE:RELIANCE", "TCS.NS": "NSE:TCS", "INFY.NS": "NSE:INFY",
        "HDFCBANK.NS": "NSE:HDFCBANK", "ICICIBANK.NS": "NSE:ICICIBANK",
        "^NSEI": "NSE:NIFTY50", "^NSEBANK": "NSE:BANKNIFTY", "NIFTY50.NS": "NSE:NIFTY50",
        "GC=F": "MCX:GOLD", "SI=F": "MCX:SILVER", "CL=F": "MCX:CRUDEOIL",
        "BTC/USDT": "BINANCE:BTCUSDT", "ETH/USDT": "BINANCE:ETHUSDT",
    }
    return mapping.get(raw, raw)


async def _fetch_yfinance(symbols: list[str]) -> list[MarketTick]:
    try:
        import yfinance as yf
        ticks: list[MarketTick] = []
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                info = tickers.tickers[sym].fast_info
                price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                volume = getattr(info, "three_month_average_volume", 0) or 0
                if price:
                    exchange = "NSE" if (".NS" in sym or "^N" in sym) else "COMEX"
                    ticks.append(MarketTick(
                        symbol=_map_symbol(sym),
                        price=float(price),
                        volume=float(volume),
                        ts=datetime.now(timezone.utc),
                        source="yfinance",
                        exchange=exchange,
                    ))
            except Exception as exc:
                logger.warning("yfinance_symbol_error", symbol=sym, error=str(exc))
        return ticks
    except ImportError:
        logger.warning("yfinance_not_installed")
        return []


async def _fetch_crypto_ccxt() -> list[MarketTick]:
    try:
        import ccxt.async_support as ccxt
        exchange_client = ccxt.binance({"enableRateLimit": True})
        ticks: list[MarketTick] = []
        try:
            for sym in _CRYPTO_SYMBOLS:
                try:
                    ticker = await exchange_client.fetch_ticker(sym)
                    ticks.append(MarketTick(
                        symbol=_map_symbol(sym),
                        price=float(ticker["last"]),
                        volume=float(ticker.get("baseVolume", 0)),
                        ts=datetime.now(timezone.utc),
                        source="ccxt_binance",
                        exchange="BINANCE",
                    ))
                except Exception as exc:
                    logger.warning("ccxt_symbol_error", symbol=sym, error=str(exc))
        finally:
            await exchange_client.close()
        return ticks
    except ImportError:
        logger.warning("ccxt_not_installed")
        return []


async def _poll_loop() -> None:
    logger.info("market_data_service_started")
    while True:
        try:
            india_ticks, crypto_ticks, commodity_ticks = await asyncio.gather(
                _fetch_yfinance(_INDIA_SYMBOLS),
                _fetch_crypto_ccxt(),
                _fetch_yfinance(_COMMODITY_SYMBOLS),
                return_exceptions=True,
            )
            all_ticks: list[MarketTick] = []
            for result in (india_ticks, crypto_ticks, commodity_ticks):
                if isinstance(result, list):
                    all_ticks.extend(result)  # type: ignore[arg-type]

            for tick in all_ticks:
                await BUS.publish(MARKET_TICKS, tick.to_dict(), trace_id=tick.trace_id)

            logger.info("market_ticks_published", count=len(all_ticks))
        except Exception as exc:
            logger.error("market_data_poll_error", error=str(exc))

        await asyncio.sleep(_POLL_INTERVAL)


async def run() -> None:
    await _poll_loop()


if __name__ == "__main__":
    asyncio.run(run())
