"""Cold-tier storage — Law 6.

Queried by ID or status. Used for: orders, fills (trades), positions audit,
strategies table. This is the source of truth for everything that must survive
a process restart or be reconstructed for compliance.

Rule: if you need "what was the status of order X", it goes here.
All fills are persisted here before being acknowledged to the engine.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.core.types import ExecutionFill, OrderRequest

logger = get_logger(__name__)


async def _connect():  # type: ignore[return]
    """Get a raw asyncpg connection. Caller must close it."""
    from app.core.config import get_settings
    import asyncpg
    url = get_settings().database_url.replace("+asyncpg", "")
    return await asyncpg.connect(url)


class ColdStore:
    """PostgreSQL cold-tier operations for orders, fills, positions, strategies."""

    # ── Orders ────────────────────────────────────────────────────────────────

    async def insert_order(self, order: OrderRequest, status: str = "submitted") -> None:
        """Persist a new order to PostgreSQL. Idempotent on order_id."""
        try:
            conn = await _connect()
            await conn.execute(
                """
                INSERT INTO orders
                  (order_id, symbol, exchange, side, order_type, quantity, price, strategy_name, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (order_id) DO UPDATE SET status = EXCLUDED.status
                """,
                order.client_order_id,
                order.symbol,
                "NSE",
                order.side.upper(),
                order.order_type.upper(),
                int(order.quantity),
                order.price,
                order.strategy_name,
                status,
            )
            await conn.close()
        except Exception as exc:
            logger.error("cold_insert_order_failed", order_id=order.client_order_id, error=str(exc))

    async def update_order_status(self, order_id: str, status: str) -> None:
        try:
            conn = await _connect()
            await conn.execute(
                "UPDATE orders SET status=$1, updated_at=NOW() WHERE order_id=$2",
                status, order_id,
            )
            await conn.close()
        except Exception as exc:
            logger.error("cold_update_order_failed", order_id=order_id, error=str(exc))

    # ── Fills / Trades ────────────────────────────────────────────────────────

    async def insert_fill(self, fill: ExecutionFill) -> None:
        """Persist an execution fill (trade) to PostgreSQL."""
        try:
            conn = await _connect()
            await conn.execute(
                """
                INSERT INTO trades
                  (trade_id, order_id, symbol, exchange, side, quantity, trade_price)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (trade_id) DO NOTHING
                """,
                fill.order_id,
                fill.order_id,
                fill.symbol,
                "NSE",
                fill.side.upper(),
                int(fill.filled_qty),
                fill.avg_price,
            )
            await conn.close()
            logger.info(
                "cold_fill_persisted",
                order_id=fill.order_id,
                symbol=fill.symbol,
                qty=fill.filled_qty,
                trace_id=fill.trace_id,
            )
        except Exception as exc:
            logger.error("cold_insert_fill_failed", order_id=fill.order_id, error=str(exc))

    # ── Positions (daily snapshot) ────────────────────────────────────────────

    async def upsert_position_snapshot(
        self,
        symbol: str,
        exchange: str,
        quantity: int,
        avg_price: float,
        close_price: float,
        unrealized_pnl: float,
        realized_pnl: float = 0.0,
    ) -> None:
        try:
            conn = await _connect()
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots
                  (symbol, exchange, quantity, avg_price, close_price, market_value, unrealized_pnl, realized_pnl)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT (snapshot_date, symbol, exchange) DO UPDATE
                SET quantity=EXCLUDED.quantity,
                    avg_price=EXCLUDED.avg_price,
                    close_price=EXCLUDED.close_price,
                    market_value=EXCLUDED.market_value,
                    unrealized_pnl=EXCLUDED.unrealized_pnl,
                    realized_pnl=EXCLUDED.realized_pnl
                """,
                symbol, exchange, quantity, avg_price, close_price,
                quantity * close_price, unrealized_pnl, realized_pnl,
            )
            await conn.close()
        except Exception as exc:
            logger.warning("cold_position_snapshot_error", symbol=symbol, error=str(exc))

    # ── Strategies ────────────────────────────────────────────────────────────

    async def upsert_strategy(self, name: str, strategy_type: str, asset_class: str, status: str, weight: float, capital: float) -> None:
        try:
            conn = await _connect()
            await conn.execute(
                """
                INSERT INTO strategies (name, strategy_type, asset_class, status, allocated_capital, current_weight)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (name) DO UPDATE
                SET status=EXCLUDED.status,
                    current_weight=EXCLUDED.current_weight,
                    allocated_capital=EXCLUDED.allocated_capital
                """,
                name, strategy_type, asset_class, status, capital, weight,
            )
            await conn.close()
        except Exception as exc:
            logger.warning("cold_upsert_strategy_error", name=name, error=str(exc))

    # ── Audit queries ─────────────────────────────────────────────────────────

    async def get_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            conn = await _connect()
            rows = await conn.fetch(
                "SELECT * FROM orders ORDER BY ts DESC LIMIT $1", limit
            )
            await conn.close()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("cold_get_orders_failed", error=str(exc))
            return []

    async def get_fills(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            conn = await _connect()
            rows = await conn.fetch(
                "SELECT * FROM trades ORDER BY ts DESC LIMIT $1", limit
            )
            await conn.close()
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("cold_get_fills_failed", error=str(exc))
            return []


COLD = ColdStore()
