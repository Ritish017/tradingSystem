from __future__ import annotations

import pandas as pd
import numpy as np

from app.core.types import Signal
from app.strategies.base import BaseStrategy


class LightGBMAlphaStrategy(BaseStrategy):
    """LightGBM-based alpha prediction strategy.
    
    Predicts next-day returns using features from the feature pipeline.
    In production, this would load a trained Qlib model.
    """
    
    def __init__(self, model_name: str = "lightgbm_next_day_return", threshold: float = 0.001) -> None:
        self.model_name = model_name
        self.threshold = threshold
        self._last_price: dict[str, float] = {}
        # TODO: Load actual model from MLflow
        # self.model = mlflow.lightgbm.load_model(f"models:/{model_name}/production")

    def on_bar(self, symbol: str, close: float) -> None:
        self._last_price[symbol] = close

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del volume
        self._last_price[symbol] = price

    def generate_signal(self, symbol: str) -> Signal:
        # Placeholder: deterministic synthetic prediction
        predicted_return = ((sum(ord(c) for c in symbol) % 100) - 50) / 10_000
        confidence = 0.55
        
        if predicted_return > self.threshold:
            return Signal(
                strategy_name="lightgbm_alpha",
                symbol=symbol,
                side="buy",
                strength=min(abs(predicted_return) * 100, 1.0),
                confidence=confidence
            )
        if predicted_return < -self.threshold:
            return Signal(
                strategy_name="lightgbm_alpha",
                symbol=symbol,
                side="sell",
                strength=min(abs(predicted_return) * 100, 1.0),
                confidence=confidence
            )
        return Signal(
            strategy_name="lightgbm_alpha",
            symbol=symbol,
            side="hold",
            strength=0.0,
            confidence=0.4
        )
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate ML alpha signals for backtesting.
        
        In production, this would:
        1. Compute features via FeaturePipeline
        2. Run model.predict(features)
        3. Generate signals based on predicted returns
        """
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        # Synthetic alpha: momentum + mean reversion hybrid
        returns_5d = price_data["close"].pct_change(5)
        returns_20d = price_data["close"].pct_change(20)
        
        # Predict next-day return as weighted combination
        predicted_returns = 0.6 * returns_5d - 0.4 * returns_20d
        
        entries = predicted_returns > self.threshold
        exits = predicted_returns < -self.threshold
        
        return entries, exits

