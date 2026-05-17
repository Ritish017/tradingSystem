from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import structlog
import xxhash
from pydantic import BaseModel

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_SEEN_KEY = "scrapling:seen_hashes"
_ARTICLES_KEY = "scrapling:articles"
_MAX_ARTICLES = 500


class Article(BaseModel):
    id: str
    source: str
    title: str
    url: str
    published_at: str
    category: str
    symbol: str | None = None
    score: int = 0
    num_comments: int = 0
    ingested_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.ingested_at:
            self.ingested_at = datetime.now(timezone.utc).isoformat()


def _content_hash(title: str, url: str) -> str:
    return xxhash.xxh64(f"{title.lower().strip()}|{url}").hexdigest()


def _normalize(raw: dict[str, Any]) -> Article | None:
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or len(title) < 10:
        return None
    article_id = _content_hash(title, url)
    return Article(
        id=article_id,
        source=raw.get("source", "unknown"),
        title=title,
        url=url,
        published_at=raw.get("published_at", datetime.now(timezone.utc).isoformat()),
        category=raw.get("category", "general"),
        symbol=raw.get("symbol"),
        score=raw.get("score", 0),
        num_comments=raw.get("num_comments", 0),
    )


async def process_raw_articles(raw_items: list[dict[str, Any]]) -> list[Article]:
    """Normalize, deduplicate, and store articles. Returns only new articles."""
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    new_articles: list[Article] = []

    try:
        for raw in raw_items:
            article = _normalize(raw)
            if article is None:
                continue
            is_new = await redis.sadd(_SEEN_KEY, article.id)
            if is_new:
                new_articles.append(article)

        if new_articles:
            pipe = redis.pipeline()
            for art in new_articles:
                pipe.lpush(_ARTICLES_KEY, art.model_dump_json())
            pipe.ltrim(_ARTICLES_KEY, 0, _MAX_ARTICLES - 1)
            await pipe.execute()
            logger.info("pipeline_ingested", new_count=len(new_articles))
    finally:
        await redis.aclose()

    return new_articles


async def get_recent_articles(limit: int = 50) -> list[Article]:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw_list = await redis.lrange(_ARTICLES_KEY, 0, limit - 1)
        return [Article.model_validate_json(r) for r in raw_list]
    finally:
        await redis.aclose()
