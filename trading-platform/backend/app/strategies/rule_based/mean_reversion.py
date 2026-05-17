from __future__ import annotations

import pandas as pd
from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, lookback: int = 30, z_threshold: float = 1.5) -> None:
        self._lookback = lookback
        self._z_threshold = z_threshold
        self._prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=500))

    def on_bar(self, symbol: str, close: float) -> None:
        self._prices[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._prices[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        prices = list(self._prices[symbol])
        if len(prices) < self._lookback:
            return Signal(strategy_name="mean_reversion", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        window = prices[-self._lookback :]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        stdev = variance**0.5 if variance > 0 else 1e-9
        z_score = (prices[-1] - mean) / stdev
        if z_score >= self._z_threshold:
            return Signal(strategy_name="mean_reversion", symbol=symbol, side="sell", strength=min(abs(z_score) / 3, 1.0), confidence=0.66)
        if z_score <= -self._z_threshold:
            return Signal(strategy_name="mean_reversion", symbol=symbol, side="buy", strength=min(abs(z_score) / 3, 1.0), confidence=0.66)
        return Signal(strategy_name="mean_reversion", symbol=symbol, side="hold", strength=0.1, confidence=0.45)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate mean reversion signals for backtesting."""
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        for i in range(self._lookback, len(closes)):
            window = closes[i - self._lookback:i]
            mean = window.mean()
            std = window.std()
            z_score = (closes[i] - mean) / (std if std > 0 else 1e-9)
            
            if z_score <= -self._z_threshold:
                entries.iloc[i] = True
            elif z_score >= self._z_threshold:
                exits.iloc[i] = True
        
        return entries, exits

