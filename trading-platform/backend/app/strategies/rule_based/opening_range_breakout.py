from __future__ import annotations

import pandas as pd
from collections import defaultdict

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class OpeningRangeBreakoutStrategy(BaseStrategy):
    """Opening Range Breakout - Classic Indian intraday strategy.
    
    Logic:
    - First 15 minutes (9:15-9:30 IST) defines the opening range
    - Buy on breakout above range high
    - Sell on breakdown below range low
    - Exit at 3:15 PM (15 min before close)
    """
    
    def __init__(self, range_minutes: int = 15) -> None:
        self.range_minutes = range_minutes
        self._ranges: dict[str, dict] = defaultdict(dict)
        self._positions: dict[str, str] = {}  # "long", "short", or None
    
    def on_bar(self, symbol: str, close: float) -> None:
        pass
    
    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        pass
    
    def generate_signal(self, symbol: str) -> Signal:
        return Signal(
            strategy_name="opening_range_breakout",
            symbol=symbol,
            side="hold",
            strength=0.0,
            confidence=0.0
        )
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate intraday ORB signals.
        
        Assumes price_data has intraday bars (e.g., 5-min or 15-min).
        """
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        if not isinstance(price_data.index, pd.DatetimeIndex):
            return entries, exits
        
        # Group by date
        for date, day_data in price_data.groupby(price_data.index.date):
            if len(day_data) < 2:
                continue
            
            # First N bars define opening range
            opening_bars = day_data.iloc[:self.range_minutes // 5]  # Assuming 5-min bars
            range_high = opening_bars["high"].max()
            range_low = opening_bars["low"].min()
            
            # Check for breakouts in subsequent bars
            for idx in day_data.index[len(opening_bars):]:
                if day_data.loc[idx, "high"] > range_high:
                    entries.loc[idx] = True
                elif day_data.loc[idx, "low"] < range_low:
                    exits.loc[idx] = True
            
            # Exit at end of day (last bar)
            if len(day_data) > 0:
                exits.iloc[-1] = True
        
        return entries, exits
