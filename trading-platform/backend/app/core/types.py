"""Canonical domain-object schema — Law 4.

One definition of every event type in the system.
All external data (broker APIs, exchange feeds, HTTP payloads) is
normalized to these types at the boundary before entering the system.

Every event carries a trace_id so it can be correlated across
all layers and log entries — Law 7.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


def _new_trace() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Type aliases ──────────────────────────────────────────────────────────────

OrderSide = Literal["buy", "sell"]
SignalSide = Literal["buy", "sell", "hold"]
OrderStatus = Literal["pending", "submitted", "partial", "filled", "rejected", "cancelled"]


# ── Domain objects ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MarketTick:
    """Normalized tick from ANY data source. Source adapters must produce this."""
    symbol: str
    source: str
    price: float
    volume: float
    ts: datetime
    trace_id: str = field(default_factory=_new_trace)

    @classmethod
    def from_dict(cls, d: dict) -> "MarketTick":
        """Normalize a raw dict (from any broker/exchange) into a MarketTick."""
        return cls(
            symbol=str(d["symbol"]),
            source=str(d.get("source", "unknown")),
            price=float(d["price"]),
            volume=float(d.get("volume", 0.0)),
            ts=datetime.fromisoformat(d["ts"]) if isinstance(d.get("ts"), str) else _utcnow(),
            trace_id=str(d.get("_trace_id") or _new_trace()),
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "price": self.price,
            "volume": self.volume,
            "ts": self.ts.isoformat(),
            "_trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class Signal:
    """Trading signal produced by a strategy."""
    strategy_name: str
    symbol: str
    side: SignalSide
    strength: float
    confidence: float
    ts: datetime = field(default_factory=_utcnow)
    trace_id: str = field(default_factory=_new_trace)


@dataclass(frozen=True)
class AggregatedSignal:
    """Weighted ensemble of multiple signals for one symbol."""
    symbol: str
    side: SignalSide
    weighted_strength: float
    weighted_confidence: float
    votes: list[Signal]
    ts: datetime = field(default_factory=_utcnow)
    trace_id: str = field(default_factory=_new_trace)


@dataclass(frozen=True)
class OrderRequest:
    """Validated order intent created by the engine after risk approval."""
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_type: str = "market"
    strategy_name: str | None = None
    trace_id: str = field(default_factory=_new_trace)


@dataclass(frozen=True)
class ExecutionFill:
    """Fill record returned by any execution adapter."""
    order_id: str
    symbol: str
    side: OrderSide
    requested_qty: float
    filled_qty: float
    avg_price: float
    status: OrderStatus
    fee: float
    slippage_bps: float
    ts: datetime = field(default_factory=_utcnow)
    trace_id: str = field(default_factory=_new_trace)


@dataclass(frozen=True)
class RiskDecision:
    """Result from the RiskGate evaluation."""
    allowed: bool
    reason: str
    trace_id: str = field(default_factory=_new_trace)
