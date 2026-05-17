from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NautilusEngineConfig:
    mode: str = "paper"
    account_currency: str = "INR"
    venues: list[str] = field(default_factory=lambda: ["NSE", "NFO", "MCX", "BINANCE"])
    max_latency_ms: int = 50
    idempotency_enabled: bool = True

