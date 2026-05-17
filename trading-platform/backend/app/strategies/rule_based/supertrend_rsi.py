from __future__ import annotations

import pandas as pd
from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class SupertrendRSIStrategy(BaseStrategy):
    def __init__(self, rsi_buy_threshold: float = 55.0, rsi_sell_threshold: float = 45.0) -> None:
        self._rsi_buy = rsi_buy_threshold
        self._rsi_sell = rsi_sell_threshold
        self._history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=30))

    def on_bar(self, symbol: str, close: float) -> None:
        self._history[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._history[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        prices = list(self._history[symbol])
        if len(prices) < 15:
            return Signal(strategy_name="supertrend_rsi", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        gains = [max(prices[i] - prices[i - 1], 0.0) for i in range(1, len(prices))]
        losses = [max(prices[i - 1] - prices[i], 0.0) for i in range(1, len(prices))]
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14 if sum(losses[-14:]) > 0 else 1e-9
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        if rsi >= self._rsi_buy:
            return Signal(strategy_name="supertrend_rsi", symbol=symbol, side="buy", strength=(rsi - 50) / 50, confidence=0.65)
        if rsi <= self._rsi_sell:
            return Signal(strategy_name="supertrend_rsi", symbol=symbol, side="sell", strength=(50 - rsi) / 50, confidence=0.65)
        return Signal(strategy_name="supertrend_rsi", symbol=symbol, side="hold", strength=0.1, confidence=0.4)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate entry/exit signals for backtesting.
        
        Returns:
            (entries, exits) as boolean Series
        """
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        for i in range(14, len(closes)):
            window = closes[i-14:i+1]
            gains = [max(window[j] - window[j-1], 0.0) for j in range(1, len(window))]
            losses = [max(window[j-1] - window[j], 0.0) for j in range(1, len(window))]
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14 if sum(losses) > 0 else 1e-9
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            if rsi >= self._rsi_buy:
                entries.iloc[i] = True
            elif rsi <= self._rsi_sell:
                exits.iloc[i] = True
        
        return entries, exits

