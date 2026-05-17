"""Canonical topic/channel names for the entire platform — Law 1.

Every component that publishes or subscribes imports its topic from here.
No string literals allowed elsewhere.
"""
from __future__ import annotations

# ── Redpanda / Kafka topics (durable, ordered, multi-consumer) ────────────────
MARKET_TICKS = "market_ticks"
RAW_NEWS = "raw_news"
MACRO_DATA = "macro_data"
NORMALIZED_DATA = "normalized_data"
FEATURES = "features"
NEWS_SIGNALS = "news_signals"
UNIFIED_SIGNAL = "unified_signal"
DEAD_LETTER = "dead_letter_queue"

# ── Redis pub/sub channels (ephemeral, fan-out) ───────────────────────────────
CHAN_TICKS_INDIA = "ticks:india"
CHAN_TICKS_CRYPTO = "ticks:crypto"
CHAN_ORDER_UPDATES = "order_updates"


def candles_channel(timeframe: str) -> str:
    """e.g. candles_channel('1m') → 'candles:1m'"""
    return f"candles:{timeframe}"


# ── Redis key prefixes (hot-tier cache) ───────────────────────────────────────
KEY_TICK = "tick:{symbol}"
KEY_LTP = "ltp:{exchange}:{token}"
KEY_QUOTE = "quote:{exchange}:{token}"
KEY_SIGNAL = "signal:{asset}"
KEY_CANDLES = "candles:{symbol}:{timeframe}"
KEY_INST_SYM = "inst:sym:{exchange}:{symbol}"
KEY_INST_TOK = "inst:tok:{exchange}:{token}"


def tick_key(symbol: str) -> str:
    return KEY_TICK.format(symbol=symbol)


def signal_key(asset: str) -> str:
    return KEY_SIGNAL.format(asset=asset)


def candles_key(symbol: str, timeframe: str) -> str:
    return KEY_CANDLES.format(symbol=symbol, timeframe=timeframe)
