from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

import numpy as np
import pandas as pd


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=length - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=length - 1, adjust=False).mean()


def _supertrend(df: pd.DataFrame, length: int = 10, multiplier: float = 3.0) -> pd.Series:
    atr = _atr(df, length)
    hl2 = (df["high"] + df["low"]) / 2
    raw_upper = (hl2 + multiplier * atr).to_numpy()
    raw_lower = (hl2 - multiplier * atr).to_numpy()
    close = df["close"].to_numpy()
    n = len(close)

    upper = raw_upper.copy()
    lower = raw_lower.copy()
    supertrend = np.full(n, np.nan)

    for i in range(1, n):
        lower[i] = max(raw_lower[i], lower[i - 1]) if close[i - 1] >= lower[i - 1] else raw_lower[i]
        upper[i] = min(raw_upper[i], upper[i - 1]) if close[i - 1] <= upper[i - 1] else raw_upper[i]

        prev = supertrend[i - 1]
        if np.isnan(prev) or prev == upper[i - 1]:
            supertrend[i] = lower[i] if close[i] > upper[i] else upper[i]
        else:
            supertrend[i] = upper[i] if close[i] < lower[i] else lower[i]

    return pd.Series(supertrend, index=df.index)


def compute_indicators(df: pd.DataFrame, indicator_set: Sequence[str]) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("DataFrame must include 'close' column")

    out = df.copy()
    for indicator in indicator_set:
        if indicator == "rsi_14":
            out[indicator] = _rsi(out["close"], 14)
        elif indicator == "ema_20":
            out[indicator] = _ema(out["close"], 20)
        elif indicator == "ema_50":
            out[indicator] = _ema(out["close"], 50)
        elif indicator == "returns_1d":
            out[indicator] = out["close"].pct_change(1)
        elif indicator == "returns_5d":
            out[indicator] = out["close"].pct_change(5)
        elif indicator == "volatility_20d":
            out[indicator] = out["close"].pct_change().rolling(20).std()
        elif indicator == "volume_zscore_20d":
            rolling = out["volume"].rolling(20)
            out[indicator] = (out["volume"] - rolling.mean()) / rolling.std().replace(0, 1e-9)
        elif indicator == "atr_14":
            out[indicator] = _atr(out, 14)
        elif indicator == "supertrend_10_3":
            out[indicator] = _supertrend(out, length=10, multiplier=3.0)
        else:
            raise ValueError(f"Unknown indicator: {indicator}")
    return out


def feature_hash(df: pd.DataFrame, indicator_set: Sequence[str]) -> str:
    payload = {
        "index": [str(v) for v in df.index.tolist()],
        "data": df.fillna(0.0).round(8).to_dict(orient="list"),
        "indicator_set": list(sorted(indicator_set)),
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
