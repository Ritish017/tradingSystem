"""
Free Data Provider - Uses only free APIs
No API keys required for basic functionality
"""

import yfinance as yf
import ccxt
import pandas as pd
from datetime import datetime, timedelta
import asyncio
import logging
from typing import Dict, List, Callable, Optional

logger = logging.getLogger(__name__)


class FreeDataProvider:
    """
    Provides market data using free sources:
    - Yahoo Finance for Indian stocks (15-20 min delayed)
    - Binance public API for crypto (real-time)
    - NSEpy/Jugaad-data for historical
    """
    
    def __init__(self):
        self.crypto_exchange = ccxt.binance()
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        
    def get_indian_stock_price(self, symbol: str, exchange: str = "NS") -> Optional[float]:
        """
        Get current price for Indian stock
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE")
            exchange: "NS" for NSE, "BO" for BSE
            
        Returns:
            Current price (15-20 min delayed) or None
        """
        try:
            ticker = yf.Ticker(f"{symbol}.{exchange}")
            info = ticker.info
            return info.get('regularMarketPrice') or info.get('currentPrice')
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def get_indian_stock_intraday(
        self, 
        symbol: str, 
        exchange: str = "NS",
        interval: str = "1m",
        period: str = "1d"
    ) -> pd.DataFrame:
        """
        Get intraday data for Indian stock
        
        Args:
            symbol: Stock symbol
            exchange: "NS" or "BO"
            interval: "1m", "5m", "15m", "1h"
            period: "1d", "5d", "1mo"
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            ticker = yf.Ticker(f"{symbol}.{exchange}")
            data = ticker.history(period=period, interval=interval)
            return data
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_indian_stock_historical(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        exchange: str = "NS"
    ) -> pd.DataFrame:
        """Get historical daily data"""
        try:
            ticker = yf.Ticker(f"{symbol}.{exchange}")
            data = ticker.history(start=start_date, end=end_date)
            return data
        except Exception as e:
            logger.error(f"Error fetching historical for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_crypto_price(self, symbol: str = "BTC/USDT") -> Optional[float]:
        """
        Get real-time crypto price from Binance
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT", "ETH/USDT")
            
        Returns:
            Current price or None
        """
        try:
            ticker = self.crypto_exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching crypto {symbol}: {e}")
            return None
    
    def get_crypto_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1m",
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Get crypto OHLCV data
        
        Args:
            symbol: Trading pair
            timeframe: "1m", "5m", "15m", "1h", "1d"
            limit: Number of candles
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            ohlcv = self.crypto_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"Error fetching crypto OHLCV {symbol}: {e}")
            return pd.DataFrame()
    
    async def stream_prices(
        self,
        symbols: List[Dict[str, str]],
        callback: Callable,
        interval: int = 60
    ):
        """
        Stream prices by polling at regular intervals
        
        Args:
            symbols: List of dicts with 'symbol' and 'type' (stock/crypto)
            callback: Function to call with price updates
            interval: Polling interval in seconds (default 60)
            
        Example:
            symbols = [
                {'symbol': 'RELIANCE', 'type': 'stock', 'exchange': 'NS'},
                {'symbol': 'BTC/USDT', 'type': 'crypto'}
            ]
        """
        logger.info(f"Starting price stream for {len(symbols)} symbols")
        
        while True:
            for item in symbols:
                try:
                    symbol = item['symbol']
                    symbol_type = item['type']
                    
                    if symbol_type == 'stock':
                        exchange = item.get('exchange', 'NS')
                        price = self.get_indian_stock_price(symbol, exchange)
                    elif symbol_type == 'crypto':
                        price = self.get_crypto_price(symbol)
                    else:
                        continue
                    
                    if price:
                        await callback({
                            'symbol': symbol,
                            'type': symbol_type,
                            'price': price,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.error(f"Error streaming {item}: {e}")
            
            await asyncio.sleep(interval)
    
    def get_nifty50_symbols(self) -> List[str]:
        """Get NIFTY 50 constituent symbols"""
        # Top 20 NIFTY 50 stocks for demo
        return [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
            "TITAN", "BAJFINANCE", "ULTRACEMCO", "NESTLEIND", "WIPRO"
        ]
    
    def get_top_crypto_symbols(self) -> List[str]:
        """Get top crypto trading pairs"""
        return [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT",
            "SOL/USDT", "DOGE/USDT", "DOT/USDT", "MATIC/USDT", "LTC/USDT"
        ]


# Example usage
if __name__ == "__main__":
    provider = FreeDataProvider()
    
    # Test Indian stock
    print("Testing Indian Stock Data:")
    price = provider.get_indian_stock_price("RELIANCE")
    print(f"RELIANCE: ₹{price}")
    
    # Test crypto
    print("\nTesting Crypto Data:")
    btc_price = provider.get_crypto_price("BTC/USDT")
    print(f"BTC/USDT: ${btc_price}")
    
    # Test intraday
    print("\nTesting Intraday Data:")
    data = provider.get_indian_stock_intraday("TCS", interval="5m")
    print(data.tail())
    
    # Test crypto OHLCV
    print("\nTesting Crypto OHLCV:")
    crypto_data = provider.get_crypto_ohlcv("ETH/USDT", "1h", 10)
    print(crypto_data.tail())
