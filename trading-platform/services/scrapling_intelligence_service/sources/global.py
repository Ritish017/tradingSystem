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


async def scrape_reuters() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.reuters_markets)
        articles = page.css("article") or page.css("div[data-testid='MediaStoryCard']") or page.css("li.story")
        for art in articles[:20]:
            title_el = art.css_first("a[data-testid='Heading']") or art.css_first("h3 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "Reuters",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.reuters_markets),
                "published_at": _now(),
                "category": "global_markets",
            })
    except Exception as exc:
        logger.warning("reuters_scrape_error", error=str(exc))
    return results


async def scrape_investing_com() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.investing_news)
        articles = page.css("article.js-article-item") or page.css("div.largeTitle") or page.css("div.newsItem")
        for art in articles[:20]:
            title_el = art.css_first("a.title") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "Investing.com",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.investing_news),
                "published_at": _now(),
                "category": "global_markets",
            })
    except Exception as exc:
        logger.warning("investing_scrape_error", error=str(exc))
    return results


async def scrape_fed() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    url = "https://www.federalreserve.gov/newsevents/pressreleases.htm"
    try:
        page = await fetch_page(url)
        rows = page.css("div.row.eventlist") or page.css("div.pressList div.row")
        for row in rows[:10]:
            link = row.css_first("em a") or row.css_first("a")
            if not link:
                continue
            results.append({
                "source": "FederalReserve",
                "title": _safe_text(link),
                "url": "https://www.federalreserve.gov" + link.attrib.get("href", ""),
                "published_at": _now(),
                "category": "monetary_policy",
            })
    except Exception as exc:
        logger.warning("fed_scrape_error", error=str(exc))
    return results


async def scrape_imf() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    url = "https://www.imf.org/en/News"
    try:
        page = await fetch_page(url)
        articles = page.css("div.news-item") or page.css("li.news-list-item") or page.css("article")
        for art in articles[:10]:
            title_el = art.css_first("h4 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "IMF",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", url),
                "published_at": _now(),
                "category": "macro",
            })
    except Exception as exc:
        logger.warning("imf_scrape_error", error=str(exc))
    return results


async def scrape_all_global() -> list[dict[str, Any]]:
    tasks = [scrape_reuters(), scrape_investing_com(), scrape_fed(), scrape_imf()]
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for r in results_nested:
        if isinstance(r, list):
            out.extend(r)
    return out
