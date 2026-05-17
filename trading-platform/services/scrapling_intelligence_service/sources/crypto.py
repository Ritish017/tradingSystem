from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from config import get_settings
from core_fetcher import fetch_page

logger = structlog.get_logger(__name__)
settings = get_settings()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(el: Any) -> str:
    try:
        return el.text.strip() if el else ""
    except Exception:
        return ""


async def scrape_coindesk() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.coindesk)
        articles = page.css("div.article-cardstyles__StyledWrapper") or page.css("article") or page.css("div.card")
        for art in articles[:20]:
            title_el = art.css_first("h6 a") or art.css_first("h3 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "CoinDesk",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.coindesk),
                "published_at": _now(),
                "category": "crypto_news",
            })
    except Exception as exc:
        logger.warning("coindesk_scrape_error", error=str(exc))
    return results


async def scrape_cointelegraph() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.cointelegraph)
        articles = page.css("article.post-card") or page.css("li.posts-listing__item") or page.css("article")
        for art in articles[:20]:
            title_el = art.css_first("a.post-card__title-link") or art.css_first("h2 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "CoinTelegraph",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.cointelegraph),
                "published_at": _now(),
                "category": "crypto_news",
            })
    except Exception as exc:
        logger.warning("cointelegraph_scrape_error", error=str(exc))
    return results


async def scrape_binance_announcements() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.binance_announcements)
        articles = page.css("div.css-1wr4jig") or page.css("a.css-1wr4jig") or page.css("div.article-list-item")
        for art in articles[:20]:
            title_el = art.css_first("h3") or art.css_first("p") or art
            link_el = art.css_first("a") or art
            results.append({
                "source": "Binance",
                "title": _safe_text(title_el),
                "url": link_el.attrib.get("href", settings.binance_announcements) if hasattr(link_el, "attrib") else settings.binance_announcements,
                "published_at": _now(),
                "category": "crypto_exchange",
            })
    except Exception as exc:
        logger.warning("binance_scrape_error", error=str(exc))
    return results


async def scrape_all_crypto() -> list[dict[str, Any]]:
    tasks = [scrape_coindesk(), scrape_cointelegraph(), scrape_binance_announcements()]
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for r in results_nested:
        if isinstance(r, list):
            out.extend(r)
    return out
