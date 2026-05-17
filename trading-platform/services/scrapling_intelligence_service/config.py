from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraplingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Redis
    redis_url: str = "redis://localhost:6379/1"
    scrape_queue_key: str = "scrapling:queue"
    signal_channel: str = "scrapling:signals"

    # Proxy pool — comma-separated list of http://user:pass@host:port
    proxy_pool: str = ""

    # Rate limits (requests per minute per domain)
    rate_limit_default: int = 10
    rate_limit_nse: int = 5
    rate_limit_bse: int = 5

    # LLM endpoint (Nemotron 120B or compatible OpenAI-format)
    llm_api_url: str = "http://localhost:8080/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "nvidia/llama-3.1-nemotron-ultra-253b-v1"

    # Crawl intervals (seconds)
    india_interval: int = 120
    global_interval: int = 180
    crypto_interval: int = 60
    social_interval: int = 300

    # Source URLs
    nse_announcements: str = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
    bse_announcements: str = "https://www.bseindia.com/corporates/ann.html"
    moneycontrol_news: str = "https://www.moneycontrol.com/news/business/markets/"
    et_markets: str = "https://economictimes.indiatimes.com/markets/stocks/news"
    livemint: str = "https://www.livemint.com/market/stock-market-news"
    business_standard: str = "https://www.business-standard.com/markets"
    sebi_press: str = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=3&smid=0"
    rbi_press: str = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
    mcx_news: str = "https://www.mcxindia.com/market-data/spot-market-price"
    reuters_markets: str = "https://www.reuters.com/markets/"
    investing_news: str = "https://www.investing.com/news/latest-news"
    coindesk: str = "https://www.coindesk.com/markets/"
    cointelegraph: str = "https://cointelegraph.com/news"
    binance_announcements: str = "https://www.binance.com/en/support/announcement/c-48"

    @field_validator("proxy_pool", mode="before")
    @classmethod
    def strip_proxy_pool(cls, v: Any) -> str:
        return str(v).strip() if v else ""

    @property
    def proxy_list(self) -> list[str]:
        if not self.proxy_pool:
            return []
        return [p.strip() for p in self.proxy_pool.split(",") if p.strip()]


@lru_cache
def get_settings() -> ScraplingSettings:
    return ScraplingSettings()
