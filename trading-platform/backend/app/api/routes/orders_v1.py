from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.angelone import orders as ao_orders

router = APIRouter(prefix="/v1/orders", tags=["orders-v1"])


class PlaceOrderRequest(BaseModel):
    tradingsymbol: str
    symboltoken: str
    transactiontype: Literal["BUY", "SELL"]
    exchange: Literal["NSE", "BSE", "NFO", "MCX", "CDS"] = "NSE"
    ordertype: Literal["MARKET", "LIMIT", "STOPLOSS_LIMIT", "STOPLOSS_MARKET"] = "MARKET"
    producttype: Literal["DELIVERY", "CARRYFORWARD", "MARGIN", "INTRADAY", "BO"] = "INTRADAY"
    variety: Literal["NORMAL", "AMO", "STOPLOSS", "ROBO"] = "NORMAL"
    duration: Literal["DAY", "IOC"] = "DAY"
    quantity: int = Field(gt=0)
    price: float = Field(default=0.0, ge=0)
    triggerprice: float = Field(default=0.0, ge=0)
    squareoff: float = 0.0
    stoploss: float = 0.0
    trailingStopLoss: float = 0.0


class ModifyOrderRequest(BaseModel):
    orderid: str
    tradingsymbol: str
    symboltoken: str
    exchange: Literal["NSE", "BSE", "NFO", "MCX", "CDS"] = "NSE"
    ordertype: Literal["MARKET", "LIMIT", "STOPLOSS_LIMIT", "STOPLOSS_MARKET"] = "LIMIT"
    producttype: Literal["DELIVERY", "CARRYFORWARD", "MARGIN", "INTRADAY", "BO"] = "INTRADAY"
    variety: Literal["NORMAL", "AMO", "STOPLOSS", "ROBO"] = "NORMAL"
    duration: Literal["DAY", "IOC"] = "DAY"
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    triggerprice: float = 0.0


class CancelOrderRequest(BaseModel):
    orderid: str
    variety: Literal["NORMAL", "AMO", "STOPLOSS", "ROBO"] = "NORMAL"


@router.post("/place")
async def place_order(req: PlaceOrderRequest) -> dict[str, Any]:
    try:
        return await ao_orders.place_order(
            variety=req.variety,
            tradingsymbol=req.tradingsymbol,
            symboltoken=req.symboltoken,
            transactiontype=req.transactiontype,
            exchange=req.exchange,
            ordertype=req.ordertype,
            producttype=req.producttype,
            duration=req.duration,
            price=req.price,
            triggerprice=req.triggerprice,
            quantity=req.quantity,
            squareoff=req.squareoff,
            stoploss=req.stoploss,
            trailingStopLoss=req.trailingStopLoss,
        )
    except Exception as exc:
        raise HTTPException(502, f"Order placement failed: {exc}") from exc


@router.put("/modify")
async def modify_order(req: ModifyOrderRequest) -> dict[str, Any]:
    try:
        return await ao_orders.modify_order(
            variety=req.variety,
            orderid=req.orderid,
            tradingsymbol=req.tradingsymbol,
            symboltoken=req.symboltoken,
            exchange=req.exchange,
            ordertype=req.ordertype,
            producttype=req.producttype,
            duration=req.duration,
            price=req.price,
            quantity=req.quantity,
            triggerprice=req.triggerprice,
        )
    except Exception as exc:
        raise HTTPException(502, f"Order modify failed: {exc}") from exc


@router.delete("/cancel")
async def cancel_order(req: CancelOrderRequest) -> dict[str, Any]:
    try:
        return await ao_orders.cancel_order(req.variety, req.orderid)
    except Exception as exc:
        raise HTTPException(502, f"Order cancel failed: {exc}") from exc


@router.get("/book")
async def get_order_book() -> list[dict[str, Any]]:
    try:
        return await ao_orders.get_order_book()
    except Exception as exc:
        raise HTTPException(502, f"Order book fetch failed: {exc}") from exc


@router.get("/tradebook")
async def get_trade_book() -> list[dict[str, Any]]:
    try:
        return await ao_orders.get_trade_book()
    except Exception as exc:
        raise HTTPException(502, f"Trade book fetch failed: {exc}") from exc
