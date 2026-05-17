from __future__ import annotations

import pandas as pd

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class BuyAndHoldStrategy(BaseStrategy):
    """Simple buy-and-hold benchmark."""
    
    def __init__(self) -> None:
        self._entered = False
    
    def on_bar(self, symbol: str, close: float) -> None:
        pass
    
    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        pass
    
    def generate_signal(self, symbol: str) -> Signal:
        if not self._entered:
            self._entered = True
            return Signal(
                strategy_name="buy_and_hold",
                symbol=symbol,
                side="buy",
                strength=1.0,
                confidence=1.0
            )
        return Signal(
            strategy_name="buy_and_hold",
            symbol=symbol,
            side="hold",
            strength=0.0,
            confidence=1.0
        )
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Buy on first bar, hold forever."""
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        if len(entries) > 0:
            entries.iloc[0] = True
        
        return entries, exits
