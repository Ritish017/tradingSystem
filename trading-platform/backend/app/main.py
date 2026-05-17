from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from app.api.routes.backtest import router as backtest_router
from app.api.routes.learning import router as learning_router
from app.api.routes.market import router as market_router
from app.api.routes.options_chain import router as options_router
from app.api.routes.orders import router as orders_router
from app.api.routes.orders_v1 import router as orders_v1_router
from app.api.routes.pnl import router as pnl_router
from app.api.routes.portfolio_live import router as portfolio_router
from app.api.routes.positions import router as positions_router
from app.api.routes.risk import router as risk_router
from app.api.routes.strategies import router as strategies_router
from app.api.routes.system import router as system_router
from app.api.routes.ws_angelone import router as ws_angelone_router
from app.api.routes.ws_live import router as ws_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.commodities import router as commodities_router
from app.api.routes.hybrid_signals import router as hybrid_signals_router
from app.core.config import get_settings
from app.core.db import HealthChecker
from app.core.logging import configure_logging, get_logger, bind_trace_id
from app.core.metrics import METRICS_CONTENT_TYPE, render_metrics
from app.engine.service import ENGINE, start_unified_signal_consumer
from app.engine.tick_aggregator import TICK_AGGREGATOR
from app.plugins.loader import discover_all
from app.storage import COLD, HOT, WARM

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title="Trading Platform API", version="0.1.0")

# ── existing routes ──────────────────────────────────────────────────────────
app.include_router(strategies_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(positions_router, prefix="/api")
app.include_router(pnl_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(learning_router, prefix="/api")
app.include_router(ws_router)
app.include_router(intelligence_router, prefix="/api")
app.include_router(commodities_router, prefix="/api")
app.include_router(hybrid_signals_router, prefix="/api")

# ── Angel One v1 routes ───────────────────────────────────────────────────────
app.include_router(market_router, prefix="/api")
app.include_router(options_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(orders_v1_router, prefix="/api")
app.include_router(ws_angelone_router)  # already has /api/v1/ws/ prefix


class ServiceHealthModel(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class HealthzResponse(BaseModel):
    overall: Literal["ok", "degraded"]
    services: dict[str, ServiceHealthModel]


@app.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    checker = HealthChecker(settings)
    names = ["postgres", "redis", "influxdb", "redpanda", "mlflow", "grafana", "openalgo"]
    checks = await asyncio.gather(
        checker.check_postgres(),
        checker.check_redis(),
        checker.check_influxdb(),
        checker.check_redpanda(),
        checker.check_mlflow(),
        checker.check_grafana(),
        checker.check_openalgo(),
    )
    results = dict(zip(names, checks))
    overall = "ok" if all(item.status == "ok" for item in results.values()) else "degraded"
    logger.info("healthz", overall=overall, services={k: v.status for k, v in results.items()})
    return HealthzResponse(
        overall=overall,
        services={name: ServiceHealthModel(status=s.status, detail=s.detail) for name, s in results.items()},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Trading platform backend is running"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)


@app.on_event("startup")
async def startup() -> None:
    startup_trace = bind_trace_id()
    logger.info("startup_begin", trace_id=startup_trace)

    # ── Plugin discovery (Law 3) ─────────────────────────────────────────────
    counts = discover_all()
    logger.info("plugins_discovered", **counts, trace_id=startup_trace)

    # ── Storage tier warm-up log (Law 6) ─────────────────────────────────────
    logger.info("storage_tiers_ready", hot=repr(HOT), warm=repr(WARM), cold=repr(COLD), trace_id=startup_trace)

    # ── Strategy registration (config-driven) ────────────────────────────────
    ENGINE.register_strategies_from_config()

    # ── Background workers ───────────────────────────────────────────────────
    asyncio.create_task(start_unified_signal_consumer())
    asyncio.create_task(TICK_AGGREGATOR.run())

    logger.info("startup_complete", trace_id=startup_trace)

    if settings.angel_enabled and settings.angel_api_key:
        from app.services.angelone.session import ANGEL_SESSION
        from app.services.angelone.instruments import INSTRUMENTS
        from app.services.angelone.orderstream import ANGEL_ORDER_STREAM
        from app.ingestion.angelone_ws import ANGEL_INGESTION
        import redis.asyncio as redis_lib
        import json

        async def _publish_order_event(event: dict) -> None:
            r = redis_lib.from_url(settings.redis_url, decode_responses=True)
            await r.publish("order_updates", json.dumps(event))
            await r.aclose()

        try:
            await ANGEL_SESSION.ensure_active()
            asyncio.create_task(INSTRUMENTS.download_and_cache())
            ANGEL_ORDER_STREAM.add_callback(_publish_order_event)
            asyncio.create_task(ANGEL_ORDER_STREAM.start())
            asyncio.create_task(ANGEL_INGESTION.run())
            logger.info("angelone_startup_complete")
        except Exception as exc:
            logger.error("angelone_startup_failed", error=str(exc))
