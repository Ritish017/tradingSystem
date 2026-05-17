from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved path to the configs/ directory — Law 5
_CONFIGS_DIR = Path(__file__).parents[3] / "configs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Plugin config paths (Law 5) ───────────────────────────────────────────
    strategies_config: str = Field(
        default=str(_CONFIGS_DIR / "strategies.yml"),
        alias="STRATEGIES_CONFIG",
    )
    agents_config: str = Field(
        default=str(_CONFIGS_DIR / "agents.yml"),
        alias="AGENTS_CONFIG",
    )
    fusion_config: str = Field(
        default=str(_CONFIGS_DIR / "fusion.yml"),
        alias="FUSION_CONFIG",
    )
    features_config: str = Field(
        default=str(_CONFIGS_DIR / "features" / "default.yml"),
        alias="FEATURES_CONFIG",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    influxdb_url: AnyUrl = Field(alias="INFLUXDB_URL")
    influxdb_org: str = Field(alias="INFLUXDB_ORG")
    influxdb_bucket: str = Field(alias="INFLUXDB_BUCKET")
    influxdb_token: str = Field(alias="INFLUXDB_TOKEN")

    redpanda_brokers: str = Field(alias="REDPANDA_BROKERS")
    redpanda_proxy_url: AnyUrl = Field(
        default="http://redpanda:8082/v1",
        alias="REDPANDA_PROXY_URL",
    )
    publish_ticks_to_external: bool = Field(default=True, alias="PUBLISH_TICKS_TO_EXTERNAL")
    mlflow_tracking_uri: AnyUrl = Field(alias="MLFLOW_TRACKING_URI")
    grafana_url: AnyUrl = Field(alias="GRAFANA_URL")
    openalgo_base_url: AnyUrl = Field(alias="OPENALGO_BASE_URL")
    binance_ws_url: str = Field(
        default="wss://stream.binance.com:9443/stream",
        alias="BINANCE_WS_URL",
    )
    kite_ws_enabled: bool = Field(default=False, alias="KITE_WS_ENABLED")

    # Hybrid Engine — legacy single-model endpoint (kept for fallback)
    llm_endpoint: str = Field(default="https://integrate.api.nvidia.com/v1/chat/completions", alias="LLM_ENDPOINT")
    llm_model: str = Field(default="nvidia/nemotron-3-super-120b-a12b", alias="LLM_MODEL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    min_signal_confidence: float = Field(default=0.6, alias="MIN_SIGNAL_CONFIDENCE")
    max_signal_age_seconds: int = Field(default=300, alias="MAX_SIGNAL_AGE_SECONDS")
    signal_conflict_threshold: float = Field(default=0.5, alias="SIGNAL_CONFLICT_THRESHOLD")

    # NVIDIA Nemotron multi-model routing
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_super_model: str = Field(default="nvidia/nemotron-3-super-120b-a12b", alias="SUPER_MODEL")
    nvidia_nano_model: str = Field(default="nvidia/nemotron-3-nano-30b-a3b", alias="NANO_MODEL")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NEMOTRON_BASE_URL")

    # Angel One SmartAPI
    angel_api_key: str = Field(default="", alias="ANGEL_API_KEY")
    angel_client_code: str = Field(default="", alias="ANGEL_CLIENT_CODE")
    angel_pin: str = Field(default="", alias="ANGEL_PIN")
    angel_totp_secret: str = Field(default="", alias="ANGEL_TOTP_SECRET")
    angel_ws_url: str = Field(
        default="wss://smartapisocket.angelone.in/smart-stream",
        alias="ANGEL_WS_URL",
    )
    angel_order_ws_url: str = Field(
        default="wss://smartapisocket.angelone.in/order-update",
        alias="ANGEL_ORDER_WS_URL",
    )
    angel_enabled: bool = Field(default=False, alias="ANGEL_ENABLED")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

