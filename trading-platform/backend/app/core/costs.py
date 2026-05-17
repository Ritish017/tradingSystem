from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Market(Enum):
    NSE_EQUITY = "nse_equity"
    NSE_FO = "nse_fo"
    BSE_EQUITY = "bse_equity"
    MCX = "mcx"
    CRYPTO = "crypto"


@dataclass
class TradeCost:
    brokerage: float
    stt: float
    exchange_txn_charge: float
    gst: float
    sebi_charges: float
    stamp_duty: float
    total: float


def calculate_indian_equity_cost(
    price: float,
    quantity: int,
    is_intraday: bool = False,
    broker: str = "zerodha",
) -> TradeCost:
    """Calculate all-in cost for NSE/BSE equity trade.
    
    Based on Zerodha brokerage calculator:
    https://zerodha.com/brokerage-calculator
    """
    turnover = price * quantity
    
    # Brokerage
    if broker == "zerodha":
        if is_intraday:
            brokerage = min(0.03 * turnover / 100, 20.0)
        else:
            brokerage = 0.0
    elif broker == "shoonya":
        brokerage = 0.0
    else:
        brokerage = 0.0
    
    # STT (Securities Transaction Tax)
    if is_intraday:
        stt = 0.025 * turnover / 100  # 0.025% on sell side only (applied on both for simplicity)
    else:
        stt = 0.1 * turnover / 100  # 0.1% on both buy and sell
    
    # Exchange transaction charges
    exchange_txn_charge = 0.00325 * turnover / 100  # NSE: 0.00325%
    
    # GST on brokerage + exchange charges
    gst = 0.18 * (brokerage + exchange_txn_charge)
    
    # SEBI charges
    sebi_charges = 0.0001 * turnover / 100  # ₹10 per crore
    
    # Stamp duty (on buy side only, applied once for simplicity)
    stamp_duty = 0.015 * turnover / 100 if not is_intraday else 0.003 * turnover / 100
    
    total = brokerage + stt + exchange_txn_charge + gst + sebi_charges + stamp_duty
    
    return TradeCost(
        brokerage=brokerage,
        stt=stt,
        exchange_txn_charge=exchange_txn_charge,
        gst=gst,
        sebi_charges=sebi_charges,
        stamp_duty=stamp_duty,
        total=total,
    )


def calculate_nfo_cost(
    price: float,
    lot_size: int,
    is_futures: bool = True,
    broker: str = "zerodha",
) -> TradeCost:
    """Calculate cost for NSE F&O trade."""
    turnover = price * lot_size
    
    # Brokerage
    if broker == "zerodha":
        brokerage = min(0.03 * turnover / 100, 20.0)
    else:
        brokerage = 0.0
    
    # STT
    if is_futures:
        stt = 0.0125 * turnover / 100  # 0.0125% on sell side
    else:
        stt = 0.05 * turnover / 100  # 0.05% on options sell side
    
    # Exchange charges
    exchange_txn_charge = 0.0019 * turnover / 100  # NSE F&O
    
    gst = 0.18 * (brokerage + exchange_txn_charge)
    sebi_charges = 0.0001 * turnover / 100
    stamp_duty = 0.002 * turnover / 100
    
    total = brokerage + stt + exchange_txn_charge + gst + sebi_charges + stamp_duty
    
    return TradeCost(
        brokerage=brokerage,
        stt=stt,
        exchange_txn_charge=exchange_txn_charge,
        gst=gst,
        sebi_charges=sebi_charges,
        stamp_duty=stamp_duty,
        total=total,
    )


def calculate_crypto_cost(
    price: float,
    quantity: float,
    exchange: str = "binance",
    is_maker: bool = False,
) -> TradeCost:
    """Calculate crypto exchange fees."""
    turnover = price * quantity
    
    if exchange == "binance":
        fee_rate = 0.1 if is_maker else 0.1  # 0.1% standard
    elif exchange == "okx":
        fee_rate = 0.08 if is_maker else 0.1
    else:
        fee_rate = 0.1
    
    brokerage = fee_rate * turnover / 100
    
    return TradeCost(
        brokerage=brokerage,
        stt=0.0,
        exchange_txn_charge=0.0,
        gst=0.0,
        sebi_charges=0.0,
        stamp_duty=0.0,
        total=brokerage,
    )


def calculate_slippage(
    price: float,
    quantity: float,
    market: Market,
    volume_participation: float = 0.01,
) -> float:
    """Estimate slippage based on market impact.
    
    Simple model: slippage = price * sqrt(quantity / avg_volume) * impact_factor
    """
    if market == Market.CRYPTO:
        impact_factor = 0.001  # 10 bps base
    elif market in (Market.NSE_EQUITY, Market.BSE_EQUITY):
        impact_factor = 0.0005  # 5 bps base
    else:
        impact_factor = 0.0003  # 3 bps for F&O
    
    # Simplified: assume slippage proportional to sqrt of participation
    slippage_bps = impact_factor * (volume_participation ** 0.5)
    return price * slippage_bps
