from __future__ import annotations

import pandas as pd
import pytest

from app.core.backtester import Backtester, BacktestConfig
from app.core.costs import (
    Market,
    calculate_crypto_cost,
    calculate_indian_equity_cost,
    calculate_nfo_cost,
    calculate_slippage,
)


def test_indian_equity_cost_intraday():
    """Test Zerodha intraday equity cost calculation."""
    cost = calculate_indian_equity_cost(price=100.0, quantity=100, is_intraday=True, broker="zerodha")
    
    # Brokerage: min(0.03% of 10000, 20) = 3.0
    assert cost.brokerage == 3.0
    
    # STT: 0.025% of 10000 = 2.5
    assert cost.stt == 2.5
    
    # Total should be positive
    assert cost.total > 0
    assert cost.total == cost.brokerage + cost.stt + cost.exchange_txn_charge + cost.gst + cost.sebi_charges + cost.stamp_duty


def test_indian_equity_cost_delivery():
    """Test delivery equity cost (higher STT)."""
    cost = calculate_indian_equity_cost(price=100.0, quantity=100, is_intraday=False, broker="zerodha")
    
    # Brokerage: 0 for delivery on Zerodha
    assert cost.brokerage == 0.0
    
    # STT: 0.1% of 10000 = 10.0
    assert cost.stt == 10.0
    
    assert cost.total > cost.stt


def test_shoonya_zero_brokerage():
    """Test Shoonya (Finvasia) zero brokerage."""
    cost = calculate_indian_equity_cost(price=100.0, quantity=100, is_intraday=True, broker="shoonya")
    
    assert cost.brokerage == 0.0
    assert cost.total > 0  # Still has STT, exchange charges, etc.


def test_nfo_futures_cost():
    """Test F&O futures cost."""
    cost = calculate_nfo_cost(price=18000.0, lot_size=50, is_futures=True, broker="zerodha")
    
    # Turnover = 18000 * 50 = 900000
    # Brokerage: min(0.03% of 900000, 20) = 20.0 (capped)
    assert cost.brokerage == 20.0
    
    # STT: 0.0125% of 900000 = 112.5
    assert cost.stt == 112.5
    
    assert cost.total > 130


def test_crypto_cost():
    """Test crypto exchange fees."""
    cost = calculate_crypto_cost(price=50000.0, quantity=0.1, exchange="binance")
    
    # Turnover = 5000
    # Fee: 0.1% = 5.0
    assert cost.brokerage == 5.0
    assert cost.total == 5.0
    assert cost.stt == 0.0  # No STT on crypto


def test_slippage_calculation():
    """Test slippage estimation."""
    slippage = calculate_slippage(price=100.0, quantity=100, market=Market.NSE_EQUITY, volume_participation=0.01)
    
    # Should be small positive value
    assert slippage > 0
    assert slippage < 1.0  # Less than 1% of price


def generate_test_data(days: int = 100) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="D")
    df = pd.DataFrame({
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0 + pd.Series(range(days)) * 0.5,  # Uptrend
        "volume": 1000000,
    }, index=dates)
    return df


def test_backtester_simple_strategy():
    """Test backtester with simple buy-and-hold."""
    price_data = generate_test_data(100)
    
    # Buy on first day, hold
    entries = pd.Series(False, index=price_data.index)
    entries.iloc[0] = True
    exits = pd.Series(False, index=price_data.index)
    
    config = BacktestConfig(initial_capital=100000.0, market=Market.NSE_EQUITY)
    backtester = Backtester(config)
    result = backtester.run(price_data, entries, exits, size=100)
    
    # Should have positive return (uptrend)
    assert result.total_return > 0
    assert result.total_trades >= 1
    assert result.sharpe_ratio > 0


def test_backtester_no_trades():
    """Test backtester with no signals."""
    price_data = generate_test_data(50)
    
    entries = pd.Series(False, index=price_data.index)
    exits = pd.Series(False, index=price_data.index)
    
    config = BacktestConfig(initial_capital=100000.0)
    backtester = Backtester(config)
    result = backtester.run(price_data, entries, exits)
    
    assert result.total_trades == 0
    assert result.total_return == 0.0
    assert result.win_rate == 0.0
