from __future__ import annotations

from typing import Any

from app.cross_market.models import CorrelationPair

# Key cross-market relationships to track
_PAIRS = [
    ("GOLD", "DXY"),
    ("GOLD", "USDINR"),
    ("SILVER", "GOLD"),
    ("BTC", "NASDAQ"),
    ("CRUDE", "USDINR"),
    ("US10Y", "NIFTY"),
    ("GOLD", "US_REAL_YIELD"),
]


def compute_correlations(price_series: dict[str, list[float]], window: int = 30) -> list[CorrelationPair]:
    """Compute rolling correlations between asset pairs."""
    try:
        import numpy as np
        from scipy.stats import spearmanr
    except ImportError:
        return []

    results: list[CorrelationPair] = []
    for asset_a, asset_b in _PAIRS:
        a_data = price_series.get(asset_a, [])
        b_data = price_series.get(asset_b, [])
        n = min(len(a_data), len(b_data), window)
        if n < 10:
            continue
        a = np.array(a_data[-n:], dtype=float)
        b = np.array(b_data[-n:], dtype=float)
        if np.std(a) == 0 or np.std(b) == 0:
            continue
        pearson = float(np.corrcoef(a, b)[0, 1])
        spearman_r, _ = spearmanr(a, b)
        results.append(CorrelationPair(
            asset_a=asset_a,
            asset_b=asset_b,
            pearson=round(pearson, 4),
            spearman=round(float(spearman_r), 4),
            window_days=n,
        ))
    return results


def get_mock_correlations() -> list[CorrelationPair]:
    """Return static correlations when live data unavailable."""
    return [
        CorrelationPair(asset_a="GOLD", asset_b="DXY", pearson=-0.72, spearman=-0.68, window_days=30),
        CorrelationPair(asset_a="GOLD", asset_b="USDINR", pearson=0.65, spearman=0.61, window_days=30),
        CorrelationPair(asset_a="SILVER", asset_b="GOLD", pearson=0.88, spearman=0.85, window_days=30),
        CorrelationPair(asset_a="BTC", asset_b="NASDAQ", pearson=0.58, spearman=0.55, window_days=30),
        CorrelationPair(asset_a="CRUDE", asset_b="USDINR", pearson=0.42, spearman=0.39, window_days=30),
        CorrelationPair(asset_a="US10Y", asset_b="NIFTY", pearson=-0.35, spearman=-0.31, window_days=30),
    ]
