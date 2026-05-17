from __future__ import annotations

import pandas as pd
from collections import defaultdict, deque

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class LSTMAlphaStrategy(BaseStrategy):
    """LSTM-based sequence prediction strategy.
    
    Uses recurrent neural network to predict price direction
    based on historical sequences.
    """
    
    def __init__(self, seq_len: int = 32, threshold: float = 0.002) -> None:
        self._seq_len = seq_len
        self.threshold = threshold
        self._series: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=512))
        # TODO: Load trained LSTM model from MLflow

    def on_bar(self, symbol: str, close: float) -> None:
        self._series[symbol].append(close)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._series[symbol].append(price)

    def generate_signal(self, symbol: str) -> Signal:
        values = list(self._series[symbol])
        if len(values) < self._seq_len:
            return Signal(strategy_name="lstm_alpha", symbol=symbol, side="hold", strength=0.0, confidence=0.0)
        drift = (values[-1] - values[-self._seq_len]) / max(values[-self._seq_len], 1e-9)
        confidence = 0.58
        if drift > self.threshold:
            return Signal(strategy_name="lstm_alpha", symbol=symbol, side="buy", strength=min(abs(drift) * 10, 1.0), confidence=confidence)
        if drift < -self.threshold:
            return Signal(strategy_name="lstm_alpha", symbol=symbol, side="sell", strength=min(abs(drift) * 10, 1.0), confidence=confidence)
        return Signal(strategy_name="lstm_alpha", symbol=symbol, side="hold", strength=0.0, confidence=0.4)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate LSTM alpha signals for backtesting."""
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        # Synthetic LSTM prediction: exponentially weighted momentum
        for i in range(self._seq_len, len(closes)):
            window = closes[i - self._seq_len:i]
            weights = [1.1 ** j for j in range(self._seq_len)]
            weighted_avg = sum(w * p for w, p in zip(weights, window)) / sum(weights)
            predicted_direction = (closes[i] - weighted_avg) / weighted_avg
            
            if predicted_direction > self.threshold:
                entries.iloc[i] = True
            elif predicted_direction < -self.threshold:
                exits.iloc[i] = True
        
        return entries, exits

