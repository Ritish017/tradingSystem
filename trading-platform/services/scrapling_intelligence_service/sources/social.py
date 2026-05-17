from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from core_fetcher import fetch_page

logger = structlog.get_logger(__name__)

_REDDIT_SUBS = [
    ("IndianStreetBets", "https://www.reddit.com/r/IndianStreetBets/new/.json?limit=25"),
    ("wallstreetbets", "https://www.reddit.com/r/wallstreetbets/new/.json?limit=25"),
    ("CryptoCurrency", "https://www.reddit.com/r/CryptoCurrency/new/.json?limit=25"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def scrape_reddit(subreddit: str, json_url: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        from core_fetcher import fetch_json
        data = await fetch_json(json_url, headers={"User-Agent": "trading-intelligence-bot/1.0"})
        posts = data.get("data", {}).get("children", [])
        for post in posts[:20]:
            d = post.get("data", {})
            title = d.get("title", "")
            if not title:
                continue
            results.append({
                "source": f"Reddit/{subreddit}",
                "title": title,
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "published_at": _now(),
                "category": "social",
                "score": d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
            })
    except Exception as exc:
        logger.warning("reddit_scrape_error", subreddit=subreddit, error=str(exc))
    return results


async def scrape_telegram_preview(channel_url: str, channel_name: str) -> list[dict[str, Any]]:
    """Scrape public Telegram channel web preview."""
    results: list[dict[str, Any]] = []
    try:
        page = await fetch_page(f"https://t.me/s/{channel_name}")
        messages = page.css("div.tgme_widget_message_text") or page.css(".message")
        for msg in messages[:15]:
            text = msg.text.strip() if msg else ""
            if len(text) < 20:
                continue
            results.append({
                "source": f"Telegram/{channel_name}",
                "title": text[:200],
                "url": channel_url,
                "published_at": _now(),
                "category": "social",
            })
    except Exception as exc:
        logger.warning("telegram_scrape_error", channel=channel_name, error=str(exc))
    return results


async def scrape_all_social() -> list[dict[str, Any]]:
    tasks = [scrape_reddit(sub, url) for sub, url in _REDDIT_SUBS]
    # Public financial Telegram channels
    tasks += [
        scrape_telegram_preview("https://t.me/s/NSEIndia", "NSEIndia"),
        scrape_telegram_preview("https://t.me/s/BSEIndia", "BSEIndia"),
    ]
    results_nested = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for r in results_nested:
        if isinstance(r, list):
            out.extend(r)
    return out
