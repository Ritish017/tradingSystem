from __future__ import annotations

import json
from collections.abc import Sequence

import pandas as pd
import redis.asyncio as redis

from app.core.config import get_settings
from app.features.indicators import feature_hash


class FeatureCache:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = redis.from_url(settings.redis_url, decode_responses=True)
        self._ttl_seconds = 24 * 60 * 60

    @staticmethod
    def _key(symbol: str, bar_size: str, indicator_set: Sequence[str], data_hash: str) -> str:
        joined = ",".join(sorted(indicator_set))
        return f"features:{symbol}:{bar_size}:{joined}:{data_hash}"

    async def get(self, symbol: str, bar_size: str, indicator_set: Sequence[str], df: pd.DataFrame) -> pd.DataFrame | None:
        data_hash = feature_hash(df, indicator_set)
        key = self._key(symbol, bar_size, indicator_set, data_hash)
        cached = await self._client.get(key)
        if cached is None:
            return None
        payload = json.loads(cached)
        return pd.DataFrame(payload)

    async def set(self, symbol: str, bar_size: str, indicator_set: Sequence[str], source_df: pd.DataFrame, features_df: pd.DataFrame) -> None:
        data_hash = feature_hash(source_df, indicator_set)
        key = self._key(symbol, bar_size, indicator_set, data_hash)
        await self._client.set(key, json.dumps(features_df.to_dict(orient="list")), ex=self._ttl_seconds)

