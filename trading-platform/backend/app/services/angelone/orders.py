from __future__ import annotations

from typing import Any, Literal

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.services.angelone.session import ANGEL_SESSION

logger = get_logger(__name__)

_BASE = "https://apiconnect.angelone.in"

Variety = Literal["NORMAL", "AMO", "STOPLOSS", "ROBO"]
OrderType = Literal["MARKET", "LIMIT", "STOPLOSS_LIMIT", "STOPLOSS_MARKET"]
ProductType = Literal["DELIVERY", "CARRYFORWARD", "MARGIN", "INTRADAY", "BO"]
Duration = Literal["DAY", "IOC"]
Exchange = Literal["BSE", "NSE", "NFO", "MCX", "NCDEX", "CDS"]


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = await ANGEL_SESSION.get_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("status"):
        raise RuntimeError(f"angelone order error: {body.get('message')}")
    return body


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
async def _get(url: str) -> dict[str, Any]:
    headers = await ANGEL_SESSION.get_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def place_order(
    *,
    variety: Variety = "NORMAL",
    tradingsymbol: str,
    symboltoken: str,
    transactiontype: Literal["BUY", "SELL"],
    exchange: Exchange = "NSE",
    ordertype: OrderType = "MARKET",
    producttype: ProductType = "INTRADAY",
    duration: Duration = "DAY",
    price: float = 0.0,
    triggerprice: float = 0.0,
    quantity: int,
    squareoff: float = 0.0,
    stoploss: float = 0.0,
    trailingStopLoss: float = 0.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "variety": variety,
        "tradingsymbol": tradingsymbol,
        "symboltoken": symboltoken,
        "transactiontype": transactiontype,
        "exchange": exchange,
        "ordertype": ordertype,
        "producttype": producttype,
        "duration": duration,
        "price": str(price),
        "triggerprice": str(triggerprice),
        "quantity": str(quantity),
        "squareoff": str(squareoff),
        "stoploss": str(stoploss),
        "trailingStopLoss": str(trailingStopLoss),
    }
    body = await _post(f"{_BASE}/rest/secure/angelbroking/order/v1/placeOrder", payload)
    order_id = body.get("data", {}).get("orderid", "")
    logger.info(
        "angelone_order_placed",
        order_id=order_id,
        symbol=tradingsymbol,
        side=transactiontype,
        qty=quantity,
    )
    return {"order_id": order_id, "status": "submitted", "raw": body}


async def modify_order(
    *,
    variety: Variety = "NORMAL",
    orderid: str,
    tradingsymbol: str,
    symboltoken: str,
    exchange: Exchange = "NSE",
    ordertype: OrderType = "LIMIT",
    producttype: ProductType = "INTRADAY",
    duration: Duration = "DAY",
    price: float,
    quantity: int,
    triggerprice: float = 0.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "variety": variety,
        "orderid": orderid,
        "tradingsymbol": tradingsymbol,
        "symboltoken": symboltoken,
        "exchange": exchange,
        "ordertype": ordertype,
        "producttype": producttype,
        "duration": duration,
        "price": str(price),
        "quantity": str(quantity),
        "triggerprice": str(triggerprice),
    }
    body = await _post(f"{_BASE}/rest/secure/angelbroking/order/v1/modifyOrder", payload)
    logger.info("angelone_order_modified", order_id=orderid)
    return {"order_id": orderid, "status": "modified", "raw": body}


async def cancel_order(variety: Variety, orderid: str) -> dict[str, Any]:
    payload = {"variety": variety, "orderid": orderid}
    body = await _post(f"{_BASE}/rest/secure/angelbroking/order/v1/cancelOrder", payload)
    logger.info("angelone_order_cancelled", order_id=orderid)
    return {"order_id": orderid, "status": "cancelled", "raw": body}


async def get_order_book() -> list[dict[str, Any]]:
    body = await _get(f"{_BASE}/rest/secure/angelbroking/order/v1/getOrderBook")
    return body.get("data", []) or []


async def get_trade_book() -> list[dict[str, Any]]:
    body = await _get(f"{_BASE}/rest/secure/angelbroking/order/v1/getTradeBook")
    return body.get("data", []) or []
