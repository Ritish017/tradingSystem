from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradingObservation:
    price: float
    returns_1: float
    volatility_20: float
    position: float


class TradingGymEnv:
    """Minimal gym-like environment surface for RL agents."""

    def __init__(self) -> None:
        self.position = 0.0
        self.last_price = 0.0

    def step(self, action: float, price: float, tx_cost_rate: float = 0.0005) -> tuple[TradingObservation, float]:
        prev_price = self.last_price if self.last_price > 0 else price
        raw_return = (price - prev_price) / max(prev_price, 1e-9)
        trade_cost = abs(action - self.position) * tx_cost_rate
        risk_penalty = abs(action) * 0.0001
        reward = raw_return * action - trade_cost - risk_penalty
        self.position = action
        self.last_price = price
        obs = TradingObservation(price=price, returns_1=raw_return, volatility_20=abs(raw_return), position=self.position)
        return obs, reward

