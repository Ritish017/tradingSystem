"""Three-tier storage — Law 6.

HOT  → Redis (sub-ms, ephemeral): ticks, positions MTM, signal cache
WARM → InfluxDB + TimescaleDB (time-range queries): candles, option snapshots
COLD → PostgreSQL (id/status queries): orders, fills, strategies, audit log
"""
from app.storage.hot import HOT, HotStore
from app.storage.warm import WARM, WarmStore
from app.storage.cold import COLD, ColdStore

__all__ = ["HOT", "WARM", "COLD", "HotStore", "WarmStore", "ColdStore"]
