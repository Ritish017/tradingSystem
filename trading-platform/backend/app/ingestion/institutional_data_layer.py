"""
Institutional-Grade Data Ingestion with Multi-Source Failover
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class DataSource(Enum):
    ZERODHA = "zerodha"
    SHOONYA = "shoonya"
    UPSTOX = "upstox"
    BINANCE = "binance"
    OKX = "okx"


@dataclass
class TickData:
    symbol: str
    timestamp: datetime
    price: float
    volume: float
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    source: str = ""
    
    def validate(self) -> bool:
        """Validate tick data quality"""
        if self.price <= 0 or self.volume < 0:
            return False
        if self.bid and self.ask and self.bid > self.ask:
            return False
        return True


@dataclass
class OrderBookSnapshot:
    symbol: str
    timestamp: datetime
    bids: list[tuple[float, float]]  # [(price, size), ...]
    asks: list[tuple[float, float]]
    source: str
    
    def spread_bps(self) -> float:
        """Calculate bid-ask spread in basis points"""
        if not self.bids or not self.asks:
            return float('inf')
        best_bid = self.bids[0][0]
        best_ask = self.asks[0][0]
        mid = (best_bid + best_ask) / 2
        return ((best_ask - best_bid) / mid) * 10000


class DataQualityMonitor:
    """Monitor data quality in real-time"""
    
    def __init__(self):
        self.tick_counts = {}
        self.last_tick_time = {}
        self.anomaly_counts = {}
        
    def check_tick(self, tick: TickData) -> tuple[bool, str]:
        """
        Check if tick is valid
        Returns: (is_valid, reason)
        """
        # Check 1: Basic validation
        if not tick.validate():
            return False, "invalid_price_or_volume"
        
        # Check 2: Price spike detection (>10% move in 1 second)
        if tick.symbol in self.last_tick_time:
            last_time = self.last_tick_time[tick.symbol]
            time_diff = (tick.timestamp - last_time).total_seconds()
            
            if time_diff < 1:  # Within 1 second
                # TODO: Check price change vs last tick
                pass
        
        # Check 3: Stale data (>5 seconds old)
        age = (datetime.now() - tick.timestamp).total_seconds()
        if age > 5:
            return False, f"stale_data_{age:.1f}s"
        
        # Check 4: Duplicate detection
        # TODO: Implement duplicate detection
        
        self.last_tick_time[tick.symbol] = tick.timestamp
        self.tick_counts[tick.symbol] = self.tick_counts.get(tick.symbol, 0) + 1
        
        return True, "ok"
    
    def get_stats(self) -> dict:
        """Get data quality statistics"""
        return {
            "total_ticks": sum(self.tick_counts.values()),
            "symbols_tracked": len(self.tick_counts),
            "anomalies": sum(self.anomaly_counts.values()),
        }


class MultiSourceDataIngestion:
    """
    Institutional-grade data ingestion with automatic failover
    
    Priority order: Zerodha → Shoonya → Upstox
    """
    
    def __init__(self):
        self.sources = {
            DataSource.ZERODHA: None,  # Will be initialized with actual adapters
            DataSource.SHOONYA: None,
            DataSource.UPSTOX: None,
        }
        self.active_source = DataSource.ZERODHA
        self.quality_monitor = DataQualityMonitor()
        self.failover_count = 0
        
    async def connect_with_failover(self, symbols: list[str]) -> bool:
        """
        Try to connect to data sources in priority order
        """
        for source in [DataSource.ZERODHA, DataSource.SHOONYA, DataSource.UPSTOX]:
            try:
                logger.info(f"Attempting connection to {source.value}")
                # TODO: Actual connection logic
                # await self.sources[source].connect(symbols)
                self.active_source = source
                logger.info(f"Successfully connected to {source.value}")
                return True
            except Exception as exc:
                logger.warning(f"Failed to connect to {source.value}: {exc}")
                continue
        
        logger.error("All data sources failed")
        return False
    
    async def stream_ticks(self, symbols: list[str]) -> AsyncIterator[TickData]:
        """
        Stream ticks with automatic failover on connection loss
        """
        while True:
            try:
                # TODO: Actual streaming logic
                # async for tick in self.sources[self.active_source].stream(symbols):
                #     is_valid, reason = self.quality_monitor.check_tick(tick)
                #     if is_valid:
                #         yield tick
                #     else:
                #         logger.warning(f"Invalid tick: {reason}")
                
                # Placeholder
                await asyncio.sleep(0.1)
                
            except ConnectionError as exc:
                logger.error(f"Connection lost to {self.active_source.value}: {exc}")
                self.failover_count += 1
                
                # Try to reconnect to next source
                if await self.connect_with_failover(symbols):
                    logger.info(f"Failover successful to {self.active_source.value}")
                    continue
                else:
                    logger.critical("All failover attempts exhausted")
                    raise
    
    def get_health_status(self) -> dict:
        """Get health status of data ingestion"""
        return {
            "active_source": self.active_source.value,
            "failover_count": self.failover_count,
            "quality_stats": self.quality_monitor.get_stats(),
        }


class CrossMarketDataValidator:
    """
    Validate data consistency across multiple sources
    
    Example: NSE price should match BSE price (within spread)
    """
    
    def __init__(self):
        self.price_cache = {}
        
    def validate_cross_market(
        self,
        symbol: str,
        nse_price: float,
        bse_price: float,
        max_diff_pct: float = 0.5
    ) -> tuple[bool, str]:
        """
        Check if NSE and BSE prices are consistent
        
        Returns: (is_valid, reason)
        """
        if abs(nse_price - bse_price) / nse_price > (max_diff_pct / 100):
            return False, f"price_divergence_{abs(nse_price - bse_price) / nse_price * 100:.2f}%"
        
        return True, "ok"


class GlobalMacroDataFeed:
    """
    Ingest global macro data for regime detection
    """
    
    async def fetch_indices(self) -> dict[str, float]:
        """
        Fetch global indices
        
        Returns: {
            'SPX': 5000.0,
            'VIX': 15.0,
            'DXY': 103.5,
            'US10Y': 4.2,
        }
        """
        # TODO: Implement actual API calls
        # - Yahoo Finance API for SPX, VIX
        # - FRED API for DXY, US10Y
        # - NSE API for NIFTY
        
        return {
            'SPX': 5000.0,
            'VIX': 15.0,
            'DXY': 103.5,
            'US10Y': 4.2,
            'NIFTY': 22000.0,
        }
    
    async def fetch_economic_calendar(self) -> list[dict]:
        """
        Fetch upcoming economic events
        
        Returns: [
            {
                'date': '2024-06-15',
                'event': 'RBI Policy Meeting',
                'importance': 'high',
                'expected': '6.5%',
            },
            ...
        ]
        """
        # TODO: Implement economic calendar API
        # - Investing.com API
        # - Trading Economics API
        
        return []


class FXDataFeed:
    """
    USD/INR data feed (critical for crypto and gold arbitrage)
    """
    
    async def get_usdinr_spot(self) -> float:
        """Get current USD/INR spot rate"""
        # TODO: Implement
        # - NSE Currency Futures (most liquid)
        # - RBI Reference Rate (official)
        # - OANDA API (real-time)
        
        return 83.0
    
    async def get_usdinr_forward(self, days: int) -> float:
        """Get USD/INR forward rate"""
        # TODO: Implement forward curve
        return 83.0


# Example usage
async def main():
    ingestion = MultiSourceDataIngestion()
    
    symbols = ["RELIANCE", "TCS", "INFY"]
    
    if await ingestion.connect_with_failover(symbols):
        async for tick in ingestion.stream_ticks(symbols):
            print(f"Received tick: {tick}")
    
    print(ingestion.get_health_status())


if __name__ == "__main__":
    asyncio.run(main())
