"""Master Engine Service — Law 3 + Law 5 + Law 6 + Law 7.

Before (violations):
- register_default_strategies(): hardcoded list of 10 strategy names.
- submit_aggregated_signal(): imported from learning layer (cross-layer).
- Position state only in memory (wrong storage tier).

After:
- Strategies loaded from configs/strategies.yml via REGISTRY.
- No cross-layer imports.
- Every fill is persisted to cold-tier PostgreSQL.
- Every event carries trace_id through the pipeline.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.core.logging import get_logger, bind_trace_id
from app.core.state import STATE, PositionState, StrategyState
from app.core.types import AggregatedSignal, OrderRequest, Signal
from app.core.risk_config import load_risk_config
from app.engine.order_router import OrderRouter
from app.engine.position_sizer import PositionSizer
from app.engine.risk_gate import RiskGate
from app.engine.signal_aggregator import SignalAggregator
from app.storage.cold import COLD
from app.bus.event_bus import BUS
from app.bus.topics import UNIFIED_SIGNAL

_settings = get_settings()
_logger = get_logger(__name__)

_CONFIGS_DIR = Path(__file__).parents[3] / "configs"


def _load_strategies_config() -> list[dict]:
    path = Path(_settings.strategies_config)
    if not path.exists():
        _logger.warning("strategies_config_not_found", path=str(path))
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("strategies", [])


class MasterEngineService:
    def __init__(self) -> None:
        risk_cfg = load_risk_config()
        self.aggregator = SignalAggregator()
        self.sizer = PositionSizer()
        self.risk = RiskGate(
            max_daily_loss_pct=float(risk_cfg["max_daily_loss_pct"]),
            max_position_concentration_pct=float(risk_cfg["max_position_concentration_pct"]),
            max_gross_exposure_pct=float(risk_cfg["max_gross_exposure_pct"]),
            max_fo_margin_utilisation_pct=float(risk_cfg["max_fo_margin_utilisation_pct"]),
            circuit_breaker_losses=int(risk_cfg["circuit_breaker_losses"]),
        )
        self.router = OrderRouter()

    # ── Strategy registration (config-driven, not hardcoded) ─────────────────

    def register_strategies_from_config(self) -> int:
        """Load strategies.yml, populate STATE.strategies + persist to PostgreSQL.

        Zero hardcoded strategy names here — all come from config.
        """
        entries = _load_strategies_config()
        registered = 0
        for entry in entries:
            if not entry.get("enabled", True):
                continue
            name = entry["id"]
            if name not in STATE.strategies:
                STATE.strategies[name] = StrategyState(
                    name=name,
                    strategy_type=entry.get("type", "rule_based"),
                    asset_class=entry.get("asset_class", "multi"),
                    status=entry.get("status", "paper"),
                    allocated_capital=float(entry.get("initial_capital", 100_000.0)),
                    current_weight=float(entry.get("initial_weight", 0.1)),
                )
                asyncio.get_event_loop().run_until_complete(
                    COLD.upsert_strategy(
                        name=name,
                        strategy_type=entry.get("type", "rule_based"),
                        asset_class=entry.get("asset_class", "multi"),
                        status=entry.get("status", "paper"),
                        weight=float(entry.get("initial_weight", 0.1)),
                        capital=float(entry.get("initial_capital", 100_000.0)),
                    )
                )
                registered += 1
        _logger.info("strategies_registered", count=registered)
        return registered

    # kept for backward compat — now delegates to config-driven method
    def register_default_strategies(self) -> None:
        self.register_strategies_from_config()

    # ── Hybrid signal processing ──────────────────────────────────────────────

    async def process_hybrid_signal(self, signal: dict[str, Any]) -> None:
        trace_id = signal.get("_trace_id", "")
        bind_trace_id(trace_id)

        action = signal.get("action", "HOLD")
        confidence = float(signal.get("confidence", 0.0))
        asset = signal.get("asset", "")

        _logger.info(
            "hybrid_signal_received",
            asset=asset,
            action=action,
            confidence=confidence,
            trace_id=trace_id,
        )

        if action == "HOLD" or confidence < 0.7 or not asset:
            return

        side = "buy" if action == "BUY" else "sell"
        synthetic = Signal(
            strategy_name="hybrid_engine",
            symbol=asset,
            side=side,  # type: ignore[arg-type]
            strength=float(signal.get("final_score", 0.5)),
            confidence=confidence,
            ts=datetime.now(timezone.utc),
            trace_id=trace_id,
        )
        pos = STATE.positions.get(asset)
        price = pos.avg_price if pos and pos.avg_price > 0 else 0.0
        if price <= 0:
            _logger.info("hybrid_signal_no_price", asset=asset)
            return

        result = await self.submit_aggregated_signal(asset, [synthetic], price, mode="paper", trace_id=trace_id)
        _logger.info("hybrid_signal_processed", asset=asset, action=action, result=result, trace_id=trace_id)

    # ── Core signal → order → fill pipeline ──────────────────────────────────

    async def submit_aggregated_signal(
        self,
        symbol: str,
        signals: list[Signal],
        price: float,
        mode: str = "paper",
        trace_id: str = "",
    ) -> dict[str, float | str]:
        bind_trace_id(trace_id)

        aggregate: AggregatedSignal = self.aggregator.aggregate(symbol, signals)

        _logger.info(
            "engine_signal_aggregated",
            symbol=symbol,
            side=aggregate.side,
            strength=aggregate.weighted_strength,
            confidence=aggregate.weighted_confidence,
            trace_id=trace_id,
        )

        qty = self.sizer.size_for_signal(aggregate, STATE.capital, price)
        if qty <= 0:
            _logger.info("engine_signal_no_size", symbol=symbol, trace_id=trace_id)
            return {"status": "skipped", "reason": "no-size"}

        side = "buy" if aggregate.side == "buy" else "sell"
        order_id = f"{symbol}-{len(STATE.orders) + 1}"
        order = OrderRequest(
            client_order_id=order_id,
            symbol=symbol,
            side=side,  # type: ignore[arg-type]
            quantity=qty,
            price=price,
            strategy_name=signals[0].strategy_name if signals else None,
            trace_id=trace_id,
        )

        # Persist order to cold tier BEFORE routing (audit trail)
        await COLD.insert_order(order, status="pending")

        decision = self.risk.evaluate(order)
        _logger.info(
            "engine_risk_decision",
            symbol=symbol,
            allowed=decision.allowed,
            reason=decision.reason,
            trace_id=trace_id,
        )

        if not decision.allowed:
            STATE.order_status[order.client_order_id] = "rejected"
            await COLD.update_order_status(order_id, "rejected")
            return {"status": "rejected", "reason": decision.reason}

        STATE.orders[order.client_order_id] = order
        STATE.order_status[order.client_order_id] = "submitted"
        await COLD.update_order_status(order_id, "submitted")

        fill = await self.router.route(order, mode=mode)

        # Update in-memory position state (hot tier)
        pos = STATE.positions.get(symbol, PositionState(symbol=symbol))
        if fill.side == "buy":
            pos.quantity += fill.filled_qty
        else:
            pos.quantity -= fill.filled_qty
        pos.avg_price = fill.avg_price
        STATE.positions[symbol] = pos
        STATE.gross_exposure += abs(fill.filled_qty * fill.avg_price)

        # Persist fill to cold tier
        await COLD.insert_fill(fill)
        await COLD.update_order_status(order_id, fill.status)
        STATE.fills.append(fill)

        _logger.info(
            "engine_fill_complete",
            symbol=symbol,
            status=fill.status,
            filled_qty=fill.filled_qty,
            avg_price=fill.avg_price,
            trace_id=trace_id,
        )
        return {"status": fill.status, "filled_qty": fill.filled_qty, "avg_price": fill.avg_price}


ENGINE = MasterEngineService()


async def start_unified_signal_consumer() -> None:
    """Background task: subscribe to unified_signal via EventBus and feed into engine.

    Before (violation): imported kafka_utils directly from hybrid_engine layer.
    After: uses BUS (Law 1) with canonical topic constant (Law 4).
    """
    _logger.info("unified_signal_consumer_started")
    async for signal in BUS.subscribe(UNIFIED_SIGNAL, "trading-engine", "trading-engine-1"):
        try:
            await ENGINE.process_hybrid_signal(signal)
        except Exception as exc:
            _logger.error("unified_signal_processing_error", error=str(exc))
