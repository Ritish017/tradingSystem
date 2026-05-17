from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from config import get_settings
from core_fetcher import fetch_page

logger = structlog.get_logger(__name__)
settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_text(el: Any) -> str:
    try:
        return el.text.strip() if el else ""
    except Exception:
        return ""


async def scrape_nse_announcements() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.nse_announcements)
        rows = page.css("table.table tbody tr") or page.css("tr[data-symbol]") or page.css(".announcement-row")
        for row in rows[:30]:
            cells = row.css("td")
            if len(cells) < 3:
                continue
            results.append({
                "source": "NSE",
                "title": _safe_text(cells[2]) or _safe_text(cells[1]),
                "symbol": _safe_text(cells[0]),
                "url": settings.nse_announcements,
                "published_at": _now().isoformat(),
                "category": "corporate_filing",
            })
    except Exception as exc:
        logger.warning("nse_scrape_error", error=str(exc))
    return results


async def scrape_bse_announcements() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.bse_announcements)
        rows = page.css("table#tblAnnouncement tbody tr") or page.css(".ann-row")
        for row in rows[:30]:
            cells = row.css("td")
            if len(cells) < 2:
                continue
            results.append({
                "source": "BSE",
                "title": _safe_text(cells[1]) or _safe_text(cells[0]),
                "symbol": _safe_text(cells[0]),
                "url": settings.bse_announcements,
                "published_at": _now().isoformat(),
                "category": "corporate_filing",
            })
    except Exception as exc:
        logger.warning("bse_scrape_error", error=str(exc))
    return results


async def scrape_moneycontrol() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.moneycontrol_news)
        articles = (
            page.css("li.clearfix") or
            page.css("div.news_listing li") or
            page.css("article.article-list")
        )
        for art in articles[:20]:
            title_el = art.css_first("h2 a") or art.css_first("a.article-title") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "Moneycontrol",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.moneycontrol_news),
                "published_at": _now().isoformat(),
                "category": "market_news",
            })
    except Exception as exc:
        logger.warning("moneycontrol_scrape_error", error=str(exc))
    return results


async def scrape_economic_times() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.et_markets)
        articles = page.css("div.eachStory") or page.css("article") or page.css("div.story-box")
        for art in articles[:20]:
            title_el = art.css_first("h3 a") or art.css_first("h2 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "EconomicTimes",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.et_markets),
                "published_at": _now().isoformat(),
                "category": "market_news",
            })
    except Exception as exc:
        logger.warning("et_scrape_error", error=str(exc))
    return results


async def scrape_livemint() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.livemint)
        articles = page.css("div.listingNew li") or page.css("div.headline") or page.css("article")
        for art in articles[:20]:
            title_el = art.css_first("h2 a") or art.css_first("a")
            if not title_el:
                continue
            results.append({
                "source": "LiveMint",
                "title": _safe_text(title_el),
                "url": title_el.attrib.get("href", settings.livemint),
                "published_at": _now().isoformat(),
                "category": "market_news",
            })
    except Exception as exc:
        logger.warning("livemint_scrape_error", error=str(exc))
    return results


async def scrape_sebi() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.sebi_press)
        rows = page.css("table.table tr") or page.css("div.press-release-row")
        for row in rows[:15]:
            link = row.css_first("a")
            if not link:
                continue
            results.append({
                "source": "SEBI",
                "title": _safe_text(link),
                "url": link.attrib.get("href", settings.sebi_press),
                "published_at": _now().isoformat(),
                "category": "regulatory",
            })
    except Exception as exc:
        logger.warning("sebi_scrape_error", error=str(exc))
    return results


async def scrape_rbi() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(settings.rbi_press)
        rows = page.css("table.tablebg tr") or page.css("div.press-release")
        for row in rows[:15]:
            link = row.css_first("a")
            if not link:
                continue
            results.append({
                "source": "RBI",
                "title": _safe_text(link),
                "url": link.attrib.get("href", settings.rbi_press),
                "published_at": _now().isoformat(),
                "category": "monetary_policy",
            })
    except Exception as exc:
        logger.warning("rbi_scrape_error", error=str(exc))
    return results


async def scrape_all_india() -> list[dict[str, Any]]:
    import asyncio
    tasks = [
        scrape_nse_announcements(),
        scrape_bse_announcements(),
        scrape_moneycontrol(),
        scrape_economic_times(),
        scrape_livemint(),
        scrape_sebi(),
        scrape_rbi(),
    ]
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for r in results_nested:
        if isinstance(r, list):
            out.extend(r)
    return out
