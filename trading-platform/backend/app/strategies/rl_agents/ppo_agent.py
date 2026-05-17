from __future__ import annotations

import pandas as pd
from app.core.types import Signal
from app.strategies.base import BaseStrategy
from app.strategies.rl_agents.env import TradingGymEnv


class PPOAgentStrategy(BaseStrategy):
    """Proximal Policy Optimization (PPO) reinforcement learning agent.
    
    Learns optimal trading policy through trial and error.
    In production, loads trained agent from MLflow.
    """
    
    def __init__(self, threshold: float = 0.1) -> None:
        self.env = TradingGymEnv()
        self.threshold = threshold
        self._action = 0.0
        # TODO: Load trained PPO model from FinRL/MLflow
        # self.agent = load_ppo_agent("models:/ppo_trading/production")

    def on_bar(self, symbol: str, close: float) -> None:
        del symbol
        _, reward = self.env.step(self._action, close)
        self._action = max(min(reward * 50, 1.0), -1.0)

    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        del symbol, volume
        _, reward = self.env.step(self._action, price)
        self._action = max(min(reward * 50, 1.0), -1.0)

    def generate_signal(self, symbol: str) -> Signal:
        if self._action > self.threshold:
            return Signal(strategy_name="ppo_agent", symbol=symbol, side="buy", strength=abs(self._action), confidence=0.55)
        if self._action < -self.threshold:
            return Signal(strategy_name="ppo_agent", symbol=symbol, side="sell", strength=abs(self._action), confidence=0.55)
        return Signal(strategy_name="ppo_agent", symbol=symbol, side="hold", strength=0.0, confidence=0.4)
    
    def generate_signals(self, price_data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Generate PPO agent signals for backtesting."""
        closes = price_data["close"].values
        entries = pd.Series(False, index=price_data.index)
        exits = pd.Series(False, index=price_data.index)
        
        # Synthetic PPO behavior: adaptive momentum with risk penalty
        action = 0.0
        for i in range(1, len(closes)):
            returns = (closes[i] - closes[i-1]) / closes[i-1]
            reward = returns * action - abs(action) * 0.0001
            action = max(min(reward * 50, 1.0), -1.0)
            
            if action > self.threshold:
                entries.iloc[i] = True
            elif action < -self.threshold:
                exits.iloc[i] = True
        
        return entries, exits

