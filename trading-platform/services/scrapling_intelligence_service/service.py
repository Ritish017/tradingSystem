from __future__ import annotations

import asyncio

import structlog
import uvicorn
from fastapi import FastAPI

from config import get_settings
from pipeline import get_recent_articles, process_raw_articles
from signal_generator import IntelligenceSignal, generate_signals
from sources.india import scrape_all_india
from sources.global import scrape_all_global
from sources.crypto import scrape_all_crypto
from sources.social import scrape_all_social

logger = structlog.get_logger(__name__)
settings = get_settings()

app = FastAPI(title="Scrapling Intelligence Service", version="1.0.0")

_running = False


async def _crawl_cycle() -> None:
    all_raw = []
    for scraper in [scrape_all_india, scrape_all_global, scrape_all_crypto, scrape_all_social]:
        try:
            items = await scraper()
            all_raw.extend(items)
        except Exception as exc:
            logger.warning("scraper_error", scraper=scraper.__name__, error=str(exc))

    new_articles = await process_raw_articles(all_raw)
    if new_articles:
        await generate_signals(new_articles)
        logger.info("crawl_cycle_done", new_articles=len(new_articles))


async def _background_loop() -> None:
    global _running
    _running = True
    while _running:
        try:
            await _crawl_cycle()
        except Exception as exc:
            logger.error("crawl_cycle_error", error=str(exc))
        await asyncio.sleep(settings.india_interval)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(_background_loop())
    logger.info("scrapling_service_started")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _running
    _running = False


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/articles")
async def get_articles(limit: int = 50) -> list[dict]:
    articles = await get_recent_articles(limit)
    return [a.model_dump() for a in articles]


@app.post("/crawl")
async def trigger_crawl() -> dict[str, str]:
    asyncio.create_task(_crawl_cycle())
    return {"status": "crawl_triggered"}


if __name__ == "__main__":
    uvicorn.run("service:app", host="0.0.0.0", port=8001, reload=False)
