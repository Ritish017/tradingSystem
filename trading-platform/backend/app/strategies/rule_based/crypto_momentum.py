from __future__ import annotations

import pandas as pd
from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class CryptoMomentumStrategy(BaseStrategy):
    def __init__(self, lookback: int = 20) -> None:
        self._lookback = lookback
        self._prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))

    def on_bar(self, symbol: str, close: float) -> None:
        self._prices[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._prices[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        prices = list(self._prices[symbol])
        if len(prices) <= self._lookback:
            return Signal(strategy_name="crypto_momentum", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        past = prices[-self._lookback]
        current = prices[-1]
        momentum = (current - past) / max(past, 1e-9)
        if momentum > 0.01:
            return Signal(strategy_name="crypto_momentum", symbol=symbol, side="buy", strength=min(momentum * 10, 1.0), confidence=0.68)
        if momentum < -0.01:
            return Signal(strategy_name="crypto_momentum", symbol=symbol, side="sell", strength=min(abs(momentum) * 10, 1.0), confidence=0.68)
        return Signal(strategy_name="crypto_momentum", symbol=symbol, side="hold", strength=0.1, confidence=0.45)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate momentum signals for backtesting."""
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        for i in range(self._lookback, len(closes)):
            momentum = (closes[i] - closes[i - self._lookback]) / closes[i - self._lookback]
            if momentum > 0.01:
                entries.iloc[i] = True
            elif momentum < -0.01:
                exits.iloc[i] = True
        
        return entries, exits

