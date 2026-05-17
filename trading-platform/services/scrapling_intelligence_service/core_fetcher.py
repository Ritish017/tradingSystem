from __future__ import annotations

import asyncio
import itertools
import random
from typing import Any

import structlog
from scrapling.fetchers import AsyncStealthyFetcher
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

_proxy_cycle: itertools.cycle[str] | None = None
_domain_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_proxy_cycle() -> itertools.cycle[str] | None:
    global _proxy_cycle
    proxies = settings.proxy_list
    if proxies and _proxy_cycle is None:
        _proxy_cycle = itertools.cycle(proxies)
    return _proxy_cycle


def _next_proxy() -> str | None:
    cycle = _get_proxy_cycle()
    return next(cycle) if cycle else None


def _domain_semaphore(domain: str) -> asyncio.Semaphore:
    if domain not in _domain_semaphores:
        _domain_semaphores[domain] = asyncio.Semaphore(3)
    return _domain_semaphores[domain]


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def fetch_page(url: str, extra_headers: dict[str, str] | None = None) -> Any:
    """Fetch a URL using AsyncStealthyFetcher with proxy rotation and anti-bot measures."""
    domain = _extract_domain(url)
    proxy = _next_proxy()
    ua = random.choice(_USER_AGENTS)

    headers = {"User-Agent": ua, **(extra_headers or {})}

    fetcher_kwargs: dict[str, Any] = {
        "headless": True,
        "network_idle": True,
        "timeout": 30000,
    }
    if proxy:
        fetcher_kwargs["proxy"] = proxy

    async with _domain_semaphore(domain):
        try:
            fetcher = AsyncStealthyFetcher(**fetcher_kwargs)
            page = await fetcher.async_fetch(url, headers=headers)
            logger.debug("fetch_ok", url=url, domain=domain, proxy=bool(proxy))
            return page
        except Exception as exc:
            logger.warning("fetch_error", url=url, error=str(exc))
            raise


async def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """Fetch JSON endpoint (no stealth needed for APIs)."""
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers or {})
        resp.raise_for_status()
        return resp.json()
