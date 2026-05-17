from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yaml

from app.features.cache import FeatureCache
from app.features.indicators import compute_indicators
from app.features.qlib_handler import QlibFeatureHandler


class FeaturePipeline:
    """Unified pipeline for feature engineering.

    Coordinates data fetching, indicator computation, normalization,
    and caching.
    """

    def __init__(
        self,
        cache: FeatureCache | None = None,
        qlib: QlibFeatureHandler | None = None,
        config_path: str = "configs/features/default.yml",
    ) -> None:
        self.cache = cache or FeatureCache()
        self.qlib = qlib or QlibFeatureHandler()
        self.config = self._load_config(config_path)
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _load_config(path: str) -> dict:
        config_file = Path(path)
        if not config_file.exists():
            return {"indicators": {}}
        with open(config_file) as f:
            return yaml.safe_load(f)

    async def get_features(
        self,
        symbol: str,
        strategy_type: str,
        df: pd.DataFrame,
        bar_size: str = "1d",
    ) -> pd.DataFrame:
        """Process raw OHLCV data into features for a specific strategy type.

        Args:
            symbol: Ticker symbol (e.g., 'RELIANCE', 'BTCUSDT').
            strategy_type: Key in config (e.g., 'rule_based', 'ml_alpha').
            df: Raw OHLCV DataFrame.
            bar_size: Frequency of data (e.g., '1d', '1h', '1m').

        Returns:
            DataFrame with indicators and features added.
        """
        indicator_set = self.config.get("indicators", {}).get(strategy_type, [])
        if not indicator_set:
            self._logger.warning("No indicator set found for strategy type: %s", strategy_type)
            return df

        # 1. Try to fetch from cache first
        try:
            cached = await self.cache.get(symbol, bar_size, indicator_set, df)
            if cached is not None:
                self._logger.debug("Feature cache hit for %s (%s)", symbol, strategy_type)
                return cached
        except Exception as exc:
            self._logger.warning("Feature cache get failed: %s", exc)

        # 2. Compute indicators
        self._logger.debug("Computing indicators for %s (%s)", symbol, strategy_type)
        features = compute_indicators(df, indicator_set)

        # 3. Store in cache
        try:
            await self.cache.set(symbol, bar_size, indicator_set, df, features)
        except Exception as exc:
            self._logger.warning("Feature cache set failed: %s", exc)

        return features
