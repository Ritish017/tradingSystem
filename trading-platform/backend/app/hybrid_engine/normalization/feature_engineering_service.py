"""Feature Engineering Service

Consumes: normalized_data
Produces: features

Market features: RSI-14, EMA-9/21/50, VWAP, ATR-14, Momentum-10
News features:   keyword_score (bullish/bearish word count ratio)
Macro features:  risk_on_score, usd_strength_zscore
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.hybrid_engine.kafka_utils import consume, publish

logger = get_logger(__name__)
settings = get_settings()

# Rolling window sizes
_RSI_PERIOD = 14
_EMA_PERIODS = (9, 21, 50)
_ATR_PERIOD = 14
_MOM_PERIOD = 10
_VWAP_MAX = 390  # max intraday bars
_MACRO_WINDOW = 20  # for z-score

_BULLISH_WORDS = {"surge", "rally", "gain", "rise", "positive", "growth", "beat", "upgrade", "buy", "profit", "record"}
_BEARISH_WORDS = {"fall", "drop", "crash", "loss", "negative", "miss", "downgrade", "sell", "cut", "ban", "fraud", "default"}


# ── Per-symbol price/volume history ──────────────────────────────────────────

class _SymbolState:
    def __init__(self) -> None:
        self.closes: deque[float] = deque(maxlen=max(_RSI_PERIOD, max(_EMA_PERIODS), _MOM_PERIOD) + 5)
        self.highs: deque[float] = deque(maxlen=_ATR_PERIOD + 5)
        self.lows: deque[float] = deque(maxlen=_ATR_PERIOD + 5)
        self.volumes: deque[float] = deque(maxlen=_VWAP_MAX)
        self.vwap_pv: float = 0.0   # cumulative price*volume
        self.vwap_v: float = 0.0    # cumulative volume
        self.ema: dict[int, float] = {}


_states: dict[str, _SymbolState] = defaultdict(_SymbolState)

# ── Macro history for z-score ─────────────────────────────────────────────────
_dxy_history: deque[float] = deque(maxlen=_MACRO_WINDOW)
_last_macro: dict[str, Any] = {}


# ── Indicator math ────────────────────────────────────────────────────────────

def _ema(prices: list[float], period: int, prev: float | None) -> float:
    k = 2 / (period + 1)
    if prev is None:
        return float(np.mean(prices[-period:])) if len(prices) >= period else prices[-1]
    return prices[-1] * k + prev * (1 - k)


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, period + 1):
        idx = -(period + 1 - i)
        h, l, pc = highs[idx], lows[idx], closes[idx - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(float(np.mean(trs)), 4)


def _momentum(closes: list[float], period: int = 10) -> float | None:
    if len(closes) < period + 1:
        return None
    return round((closes[-1] - closes[-(period + 1)]) / max(closes[-(period + 1)], 1e-9), 6)


def _keyword_score(title: str) -> float:
    words = set(title.lower().split())
    bull = len(words & _BULLISH_WORDS)
    bear = len(words & _BEARISH_WORDS)
    total = bull + bear
    if total == 0:
        return 0.0
    return round((bull - bear) / total, 3)  # -1 to 1


def _risk_on_score(macro: dict[str, Any]) -> float:
    sp = macro.get("sp500_change_pct") or 0.0
    nifty = macro.get("nifty_change_pct") or 0.0
    vix = macro.get("vix") or 20.0
    vix_norm = max(0.0, min(1.0, (vix - 10) / 40))  # 10→0, 50→1
    return round(((sp + nifty) / 2) * 0.5 - vix_norm * 0.5, 4)


def _usd_strength_zscore(dxy: float) -> float:
    _dxy_history.append(dxy)
    if len(_dxy_history) < 5:
        return 0.0
    arr = np.array(_dxy_history)
    std = arr.std()
    if std < 1e-9:
        return 0.0
    return round(float((dxy - arr.mean()) / std), 4)


# ── Handlers per data type ────────────────────────────────────────────────────

async def _handle_tick(record: dict[str, Any]) -> None:
    symbol = record.get("symbol", "")
    price = record.get("price")
    volume = record.get("volume")
    if not symbol or price is None:
        return

    price = float(price)
    volume = float(volume or 0)
    st = _states[symbol]

    st.closes.append(price)
    st.highs.append(price)   # tick-level: high=low=close
    st.lows.append(price)
    st.volumes.append(volume)
    st.vwap_pv += price * volume
    st.vwap_v += volume

    closes = list(st.closes)
    highs = list(st.highs)
    lows = list(st.lows)

    # EMAs
    for period in _EMA_PERIODS:
        st.ema[period] = _ema(closes, period, st.ema.get(period))

    vwap = round(st.vwap_pv / max(st.vwap_v, 1e-9), 4)
    rsi = _rsi(closes)
    atr = _atr(highs, lows, closes)
    mom = _momentum(closes)

    feature = {
        "type": "market_feature",
        "symbol": symbol,
        "price": price,
        "rsi_14": rsi,
        "ema_9": round(st.ema.get(9, price), 4),
        "ema_21": round(st.ema.get(21, price), 4),
        "ema_50": round(st.ema.get(50, price), 4),
        "vwap": vwap,
        "atr_14": atr,
        "momentum_10": mom,
        "timestamp": record.get("timestamp"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    await publish("features", feature)


async def _handle_news(record: dict[str, Any]) -> None:
    title = record.get("title", "")
    entities = record.get("entities") or []
    score = _keyword_score(title)

    feature = {
        "type": "news_feature",
        "id": record.get("id", ""),
        "title": title,
        "entities": entities,
        "keyword_score": score,
        "source": record.get("source", ""),
        "category": record.get("category", ""),
        "timestamp": record.get("timestamp"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    await publish("features", feature)


async def _handle_macro(record: dict[str, Any]) -> None:
    _last_macro.update(record)
    dxy = record.get("dxy")
    feature = {
        "type": "macro_feature",
        "risk_on_score": _risk_on_score(record),
        "usd_strength_zscore": _usd_strength_zscore(float(dxy)) if dxy else 0.0,
        "vix": record.get("vix"),
        "us10y": record.get("us10y"),
        "dxy": dxy,
        "timestamp": record.get("timestamp"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    await publish("features", feature)


async def run() -> None:
    logger.info("feature_engineering_service_started")

    async def process() -> None:
        async for record in consume("normalized_data", "features-svc", "features-svc-1"):
            try:
                rtype = record.get("type")
                if rtype == "tick":
                    await _handle_tick(record)
                elif rtype == "news":
                    await _handle_news(record)
                elif rtype == "macro":
                    await _handle_macro(record)
            except Exception as exc:
                logger.error("feature_error", error=str(exc))

    await process()


if __name__ == "__main__":
    asyncio.run(run())
