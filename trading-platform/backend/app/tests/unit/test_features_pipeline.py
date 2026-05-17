from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.features.indicators import compute_indicators, feature_hash
from app.features.normaliser import rank_normalise, zscore


def generate_dummy_data(days: int = 180) -> pd.DataFrame:
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
    df = pd.DataFrame(
        {
            "open": np.random.uniform(100, 200, size=days),
            "high": np.random.uniform(200, 300, size=days),
            "low": np.random.uniform(0, 100, size=days),
            "close": np.random.uniform(100, 200, size=days),
            "volume": np.random.uniform(1000, 5000, size=days),
        },
        index=dates,
    )
    # Ensure high is max and low is min
    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)
    return df


@pytest.mark.asyncio
async def test_compute_indicators_performance_and_determinism():
    df = generate_dummy_data(180)  # ~6 months
    indicator_set = ["rsi_14", "ema_20", "ema_50", "returns_1d", "atr_14"]

    # 1. Performance check
    start_time = time.perf_counter()
    result1 = compute_indicators(df, indicator_set)
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000

    print(f"Indicator computation took {duration_ms:.2f}ms")
    assert duration_ms < 500, f"Computation too slow: {duration_ms:.2f}ms"

    # 2. Determinism check (same input -> same output)
    result2 = compute_indicators(df, indicator_set)
    pd.testing.assert_frame_equal(result1, result2)

    # 3. Hash determinism
    hash1 = feature_hash(result1, indicator_set)
    hash2 = feature_hash(result2, indicator_set)
    assert hash1 == hash2, "Feature hash should be deterministic"


def test_normaliser():
    data = pd.Series([10, 20, 30, 40, 50])
    
    # Z-score test
    z = zscore(data)
    assert np.isclose(z.mean(), 0, atol=1e-7)
    assert np.isclose(z.std(ddof=0), 1, atol=1e-7)
    
    # Rank normalise test
    r = rank_normalise(data)
    assert r.min() == -0.6  # rank 1/5 = 0.2 -> (0.2-0.5)*2 = -0.6
    assert r.max() == 1.0   # rank 5/5 = 1.0 -> (1.0-0.5)*2 = 1.0
    # Wait, rank_normalise logic: (ranks - 0.5) * 2
    # ranks: [0.2, 0.4, 0.6, 0.8, 1.0]
    # r: [-0.6, -0.2, 0.2, 0.6, 1.0]
    assert np.isclose(r.iloc[0], -0.6)
    assert np.isclose(r.iloc[-1], 1.0)
