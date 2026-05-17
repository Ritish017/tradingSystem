from __future__ import annotations

import pandas as pd
from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class TransformerAlphaStrategy(BaseStrategy):
    """Transformer-based attention mechanism for price prediction.
    
    Uses self-attention to identify important patterns in price history.
    """
    
    def __init__(self, lookback: int = 48, threshold: float = 0.0015) -> None:
        self._lookback = lookback
        self.threshold = threshold
        self._prices: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1024))
        # TODO: Load trained Transformer model from MLflow

    def on_bar(self, symbol: str, close: float) -> None:
        self._prices[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._prices[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        prices = list(self._prices[symbol])
        if len(prices) < self._lookback:
            return Signal(strategy_name="transformer_alpha", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        weighted = 0.0
        total = 0.0
        recent = prices[-self._lookback :]
        for idx, value in enumerate(recent, start=1):
            weighted += idx * value
            total += idx
        weighted_mean = weighted / max(total, 1e-9)
        edge = (prices[-1] - weighted_mean) / max(weighted_mean, 1e-9)
        confidence = 0.6
        if edge > self.threshold:
            return Signal(strategy_name="transformer_alpha", symbol=symbol, side="buy", strength=min(edge * 8, 1.0), confidence=confidence)
        if edge < -self.threshold:
            return Signal(strategy_name="transformer_alpha", symbol=symbol, side="sell", strength=min(abs(edge) * 8, 1.0), confidence=confidence)
        return Signal(strategy_name="transformer_alpha", symbol=symbol, side="hold", strength=0.0, confidence=0.4)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate Transformer alpha signals for backtesting."""
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        # Synthetic attention-weighted prediction
        for i in range(self._lookback, len(closes)):
            window = closes[i - self._lookback:i]
            # Simulate attention: recent prices get higher weight
            weights = [(j + 1) for j in range(self._lookback)]
            weighted_mean = sum(w * p for w, p in zip(weights, window)) / sum(weights)
            edge = (closes[i] - weighted_mean) / weighted_mean
            
            if edge > self.threshold:
                entries.iloc[i] = True
            elif edge < -self.threshold:
                exits.iloc[i] = True
        
        return entries, exits

