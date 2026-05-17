from __future__ import annotations

from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class BankNiftyShortStraddleStrategy(BaseStrategy):
    def __init__(self, vol_threshold: float = 0.004) -> None:
        self._vol_threshold = vol_threshold
        self._prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=40))

    def on_bar(self, symbol: str, close: float) -> None:
        self._prices[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._prices[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        prices = list(self._prices[symbol])
        if len(prices) < 20:
            return Signal(strategy_name="bank_nifty_straddle", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        returns = [(prices[i] / prices[i - 1]) - 1 for i in range(1, len(prices))]
        mean = sum(returns[-20:]) / 20
        variance = sum((r - mean) ** 2 for r in returns[-20:]) / 20
        vol = variance**0.5
        if vol < self._vol_threshold:
            return Signal(strategy_name="bank_nifty_straddle", symbol=symbol, side="sell", strength=(self._vol_threshold - vol) / self._vol_threshold, confidence=0.65)
        return Signal(strategy_name="bank_nifty_straddle", symbol=symbol, side="hold", strength=0.15, confidence=0.4)

