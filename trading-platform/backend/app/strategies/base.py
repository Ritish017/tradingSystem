from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.types import Signal


class BaseStrategy(ABC):
    @abstractmethod
    def on_bar(self, symbol: str, close: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_tick(self, symbol: str, price: float, volume: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_signal(self, symbol: str) -> Signal:
        raise NotImplementedError

