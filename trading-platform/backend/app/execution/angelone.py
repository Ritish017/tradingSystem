from __future__ import annotations

from app.core.logging import get_logger
from app.core.types import ExecutionFill, OrderRequest
from app.execution.base import BaseExecutionAdapter
from app.services.angelone import orders as ao_orders
from app.services.angelone.instruments import INSTRUMENTS

logger = get_logger(__name__)


class AngelOneExecutionAdapter(BaseExecutionAdapter):
    adapter_id = "angelone"

    """Routes live orders through Angel One SmartAPI."""

    async def execute(self, order: OrderRequest) -> ExecutionFill:
        # Resolve symbol → token
        token = await INSTRUMENTS.symbol_to_token(order.symbol, exchange="NSE")
        exchange = "NSE"

        # Try NFO for F&O symbols
        if token is None and (order.symbol.endswith("FUT") or order.symbol.endswith("CE") or order.symbol.endswith("PE")):
            token = await INSTRUMENTS.symbol_to_token(order.symbol, exchange="NFO")
            exchange = "NFO"

        if token is None:
            logger.error("angelone_symbol_not_found", symbol=order.symbol)
            return ExecutionFill(
                order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                requested_qty=order.quantity,
                filled_qty=0.0,
                avg_price=0.0,
                status="rejected",
                fee=0.0,
                slippage_bps=0.0,
            )

        transaction_type = "BUY" if order.side == "buy" else "SELL"
        order_type = "MARKET" if order.order_type == "market" else "LIMIT"

        try:
            result = await ao_orders.place_order(
                tradingsymbol=order.symbol,
                symboltoken=token,
                transactiontype=transaction_type,  # type: ignore[arg-type]
                exchange=exchange,  # type: ignore[arg-type]
                ordertype=order_type,  # type: ignore[arg-type]
                producttype="INTRADAY",
                duration="DAY",
                price=order.price if order_type == "LIMIT" else 0.0,
                quantity=int(order.quantity),
            )
            order_id = result.get("order_id", order.client_order_id)
            logger.info(
                "angelone_order_sent",
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                qty=order.quantity,
            )
            return ExecutionFill(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                requested_qty=order.quantity,
                filled_qty=order.quantity,
                avg_price=order.price,
                status="submitted",
                fee=0.0,
                slippage_bps=0.0,
            )
        except Exception as exc:
            logger.error("angelone_order_failed", symbol=order.symbol, error=str(exc))
            return ExecutionFill(
                order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                requested_qty=order.quantity,
                filled_qty=0.0,
                avg_price=0.0,
                status="rejected",
                fee=0.0,
                slippage_bps=0.0,
            )
