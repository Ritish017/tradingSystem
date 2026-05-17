# Plan: Multi-Source Data & Broker Integration — Phases 7, 8, 9, 10(FRED)

## Context

The user supplied a large implementation prompt to add new market-data sources and
broker adapters. **Scope (user-confirmed):** Phases 7 + 8 + 9 + the FRED-provider part
of Phase 10. (Phase 10 RBI/forex was truncated in the prompt — explicitly out of scope.)

The prompt's code samples were written against an older/assumed architecture and **will
not run as-is**. The codebase was just refactored to the 7-Laws plugin architecture this
session. The user chose: *do what's best* → translate the prompt's **intent** into the
**actual** verified contracts. Key reconciliations (verified by exploration, `path:line`):

| Prompt assumes | Reality → what we do |
|---|---|
| `MarketTick(symbol, exchange, ltp, OHLC, timestamp, source)` | frozen `MarketTick(symbol, source, price, volume, ts, trace_id)` + `to_dict()` (`types.py:35-65`). Only last price+volume on the tick bus; no exchange/OHLC/ltp. |
| `app.core.redis_client.get_redis` | none — `redis.asyncio.from_url(get_settings().redis_url, decode_responses=True)` (pattern: `options.py:61-81`) |
| `from app.core.metrics import COUNTER` | `CounterMetric(name,help,labelnames)` singleton → `.labels(**kw).inc()` (`metrics.py:54-73`); `render_metrics()` is a hard-coded allowlist |
| `structlog.get_logger()` | `from app.core.logging import get_logger; get_logger(__name__)` |
| edit `order_router.py` with `elif exchange_mode==` | plugin auto-discovery — **0 edits**; adapter just sets `adapter_id` (`loader.py:72-103`, `order_router.py:37`) |
| `OrderRequest.symbol_token/.exchange_mode`; `side=="BUY"` | frozen `OrderRequest(client_order_id,symbol,side[lowercase],quantity,price,order_type,...)`; `ExecutionFill(order_id,symbol,side,requested_qty,filled_qty,avg_price,status,fee,slippage_bps,...)` |
| `commodity_intelligence_engine` in `hybrid_engine/` | actually `app/commodities/commodity_intelligence_engine.py`; consumes `FEATURES`/`NEWS_SIGNALS`, reads `_macro["gold_usd"]`, **not started in main.py** |

**Reference patterns to mirror exactly:**
- `app/ingestion/angelone_ws.py` — canonical tick normalize + publish (`publisher.publish_tick(MARKET_TICKS, tick)` + Redis `tick:{sym}` + pub/sub `ticks:india`).
- `app/services/angelone/websocket.py:46-65,99-134` — thread→asyncio bridge (`run_coroutine_threadsafe` + bounded `asyncio.Queue` drop-oldest + daemon thread + `async def stream()`).
- `app/main.py:126-148` — gated startup precedent (`if settings.X_enabled and creds: lazy import; asyncio.create_task; try/except`).
- `app/services/angelone/options.py:21-26,61-81` — tenacity retry + Redis cache idiom.

**Verified load-bearing facts:** `feature_engineering_service.py:199-209` publishes
`macro_feature` **without `gold_usd`** → commodity engine's `gold_usd` contributor is
permanently dead; a new publisher with the same `type="macro_feature"` + `gold_usd`
fixes it via `_macro.update()` merge with **zero engine edits**. `pyproject.toml` has
base `dependencies` + only a `dev` optional group; `yfinance` is absent (pre-existing).

## Guiding rules (apply throughout)

1. Every tick → canonical `MarketTick(symbol, source, price, volume, ts)`; publish via the `angelone_ws.py` path (`publisher.publish_tick` + Redis cache + pub/sub to `CHAN_TICKS_INDIA`/`CHAN_TICKS_CRYPTO`).
2. New brokers = 1 new file in `app/execution/` with `adapter_id`; **0 edits** to `order_router.py`/engine/registry/loader.
3. New WS ingesters = `BaseIngester` + `source_id`, thread→asyncio bridge per `websocket.py`, started by a NEW gated block in `main.py` (registration ≠ startup).
4. Heavy SDKs (`upstox-python-sdk`, `NorenRestApiPy`, `breeze-connect`, `python-socketio`) → optional `pyproject.toml` groups + **lazy import inside `run()`/`execute()`** under enable guards, so paper trading works without them.
5. HTTP providers (CoinGecko/CMC/Metals/Commodities/FRED) are on-demand cached singletons under a new `app/providers/` package — NOT `BaseIngester`, NOT auto-discovered. No `data_registry.py` (rejected — needless indirection).
6. Do NOT copy `market_data_service.py` (it builds `MarketTick(exchange=...)` → broken against the real 5-field type; not wired anywhere).

---

## Phase 7 — Upstox + Shoonya (ticks + execution) + ICICI Breeze options backup

**NEW files**
- `app/ingestion/upstox_ws.py` — `UpstoxTickIngestionService(BaseIngester)`, `source_id="upstox"`. Internal `_UpstoxWS` bridge mirroring `websocket.py`. Lazy `import upstox_client` in `run()`. `_parse → MarketTick(source="upstox")`. `_handle_tick` = byte-analogue of `angelone_ws.py:77-94`. Singleton `UPSTOX_INGESTION`.
- `app/ingestion/shoonya_ws.py` — `ShoonyaTickIngestionService(BaseIngester)`, `source_id="shoonya"`. Lazy `from NorenRestApiPy.NorenApi import NorenApi`. Partial-tick safe (skip if no `lp`). Singleton `SHOONYA_INGESTION`.
- `app/execution/upstox.py` — `UpstoxExecutionAdapter(BaseExecutionAdapter)`, `adapter_id="upstox"`. `execute()` mirrors `angelone.py`: enable/cred guard → `rejected` fill; success → `status="submitted"` fill; map lowercase side → `BUY/SELL`.
- `app/execution/shoonya.py` — `ShoonyaExecutionAdapter`, `adapter_id="shoonya"`. `NorenApi.place_order(buy_or_sell='B'|'S',...)`.
- `app/services/options/breeze_backup.py` — `BreezeOptionChainBackup` with **same signature** as `OptionChainService.get_option_chain` (drop-in). Lazy `from breeze_connect import BreezeConnect`. Redis-cache + tenacity per `options.py`. Singleton `BREEZE_OPTION_CHAIN`.
- `app/services/options/provider.py` — `ResilientOptionChain` façade: try `OPTION_CHAIN` → on failure & `breeze_enabled` → `BREEZE_OPTION_CHAIN`. Singleton `OPTIONS`. (Owns fallback policy in one place; keeps Angel + Breeze modules untouched.)

**EDIT existing**
- `app/core/config.py` — add `Field(alias=...)` settings: `upstox_enabled/api_key/api_secret/access_token`, `shoonya_enabled/user/password/totp_secret/api_key/vendor_code/imei`, `breeze_enabled/api_key/api_secret/session_token` (aliases match `.env.example`). Defaults keep paper mode working (`extra="ignore"`).
- `app/main.py` — two gated startup blocks (clone of `:126-148`) for Upstox & Shoonya ingesters; lazy imports inside the `if`.
- `app/api/routes/options_chain.py` — change import `OPTION_CHAIN` → `OPTIONS` and the ~5 call sites (mechanical rename; fallback logic lives in the façade).
- `pyproject.toml` — new `[project.optional-dependencies] brokers = ["upstox-python-sdk>=2.0.0", "NorenRestApiPy", "breeze-connect>=1.0.0"]` (NOT base deps).

**NOT touched:** `order_router.py`, `engine/service.py`, `plugins/{registry,loader}.py`, `core/types.py`.

---

## Phase 8 — CoinDCX (WS) + CoinGecko + CoinMarketCap (HTTP)

**NEW files**
- `app/ingestion/coindcx_ws.py` — `CoinDCXTickIngestionService(BaseIngester)`, `source_id="coindcx"`. Lazy `import socketio` (sync `socketio.Client` + thread bridge, one consistent pattern). Publish to `MARKET_TICKS` + Redis `CHAN_TICKS_CRYPTO` (deliberately the canonical path, not `crypto_ccxt.py`'s nonstandard `"ticks.crypto"`). Singleton `COINDCX_INGESTION`.
- `app/core/http_client.py` — `RateLimitedClient` (httpx.AsyncClient + asyncio lock/sleep token-bucket + tenacity retry copied from `options.py:21-26`); `CachedHTTPProvider` base with `_cached(key,ttl,fetch)` using `aioredis.from_url(...).setex(...)`. No new deps.
- `app/providers/__init__.py` (empty package marker).
- `app/providers/coingecko.py` — `CoinGeckoProvider(CachedHTTPProvider)`, singleton `COINGECKO`. `get_price`, `get_ohlcv`, `get_btc_dominance` (OHLC is a return value to API callers, never published as ticks).
- `app/providers/coinmarketcap.py` — `CoinMarketCapProvider`, singleton `CMC`. `get_listings`, `get_global_metrics`; no-key → return empty + `logger.warning`.

**EDIT existing**
- `app/core/config.py` — `coindcx_enabled/api_key/api_secret`, `coingecko_api_key`, `coinmarketcap_api_key`.
- `app/main.py` — one gated block for CoinDCX ingester (CoinGecko/CMC are on-demand, no task).
- `app/core/metrics.py` — **single sanctioned metrics edit for Phases 8–10:** add `HTTP_PROVIDER_REQUESTS_TOTAL(provider,outcome)` + `WS_INGESTER_RECONNECTS_TOTAL(source)` `CounterMetric` singletons AND append both to `render_metrics()` (else invisible at `/metrics`).
- `pyproject.toml` — `[project.optional-dependencies] data = ["python-socketio[client]>=5.11.0"]`.

**NOT touched:** engine, router, registry, loader, `types.py`, `event_bus.py`.

---

## Phase 9 — Metals + Commodities providers → commodity intelligence engine

**Wiring decision: option (b)** — a new publisher emits `macro_feature` (incl. `gold_usd`)
to the `FEATURES` topic the engine already consumes. Chosen because: (1) fixes the verified
dead `gold_usd` contributor; (2) **zero edits** to the just-refactored engine; (3) avoids a
Law-2 layer violation (engine reaching down into providers); (4) `_macro.update()` merges
keys and `feature_engineering_service` never sets `gold_usd` so it can't clobber it.

**NEW files**
- `app/providers/metals.py` — `MetalsProvider`, singleton `METALS`. `get_metals() → {XAU,XAG,XPT}`. Primary metals API; **yfinance fallback** (`GC=F/SI=F/PL=F`) mirroring `macro_data_service.py:49-72`; graceful `{}` on failure.
- `app/providers/commodities.py` — `CommoditiesProvider`, singleton `COMMODITIES`. `get_commodities() → {WTI,BRENT,NATGAS,...}`; yfinance fallback `CL=F/BZ=F/NG=F/ZC=F/ZW=F`.
- `app/ingestion/commodity_macro_publisher.py` — bare async `run()` (like `macro_data_service.py`, NOT a `BaseIngester`). 60s loop: fetch metals+commodities → `BUS.publish(FEATURES, {"type":"macro_feature","gold_usd":...,"silver_usd":...,"wti":...,...})`.

**EDIT existing**
- `app/core/config.py` — `metals_api_key/url`, `commodities_api_key/url`, `commodity_intel_enabled`.
- `app/main.py` — one gated block (flag `commodity_intel_enabled`) starting BOTH `commodity_macro_publisher.run()` and `commodity_intelligence_engine.run()` (the engine is started nowhere today).
- `pyproject.toml` — add `yfinance>=0.2.40,<1.0.0` to **base** deps (fixes pre-existing omission; fallback is otherwise non-functional).

**NOT touched:** `app/commodities/commodity_intelligence_engine.py` (the whole point of (b)), engine, router, registry, loader, types.

---

## Phase 10 (partial) — FRED provider only

**NEW file**
- `app/providers/fred.py` — `FredProvider(CachedHTTPProvider)`, singleton `FRED`. Series map (`us10y→DGS10`, `vix→VIXCLS`, `dxy→DTWEXBGS`, `cpi→CPIAUCSL`, …). `get_series(key)` (latest obs, Redis-cached ~3600s, tenacity), `get_macro_snapshot()`. No-key → `None` + warning. Bus wiring to `macro_feature` noted as a future seam, **not built** (out of stated scope).

**EDIT existing**
- `app/core/config.py` — `fred_api_key`, `fred_api_url`.

**NOT touched:** main.py (on-demand), pyproject (httpx/tenacity base), engine/router/etc.

---

## Critical files

- `backend/app/ingestion/angelone_ws.py` — canonical tick publish pattern to mirror
- `backend/app/services/angelone/websocket.py:46-65,99-134` — thread→asyncio bridge for all new WS ingesters
- `backend/app/main.py:126-148` — exact gated-startup precedent
- `backend/app/commodities/commodity_intelligence_engine.py:83,88,134-137` — Phase 9 consumer (must stay unedited)
- `backend/app/hybrid_engine/normalization/feature_engineering_service.py:199-209` — proves the `gold_usd` gap
- `backend/app/services/angelone/options.py:21-26,61-81,104` + `backend/app/api/routes/options_chain.py` — Breeze fallback seam
- `backend/app/core/{types,config,metrics,logging}.py`, `pyproject.toml:10-47` — contracts/manifest

## Risks

- **NorenRestApiPy / breeze-connect on Windows** — not cleanly on PyPI / older socketio deps; potential conflict with the `python-socketio` added for CoinDCX. Mitigated by optional groups + lazy import + gated try/except (paper unaffected). Implementer must pin exact source.
- **Breeze options schema** — downstream `pcr/maxpain/heatmap` expect Angel's row keys; `breeze_backup.py` must normalize to the same keys. Implementer reads `app/services/options/{chain,pcr,maxpain,heatmap}.py` before finalizing the normalizer (verification step, not guessable now).
- **SDK threading** — each WS SDK spawns its own thread; capture `self._loop = asyncio.get_running_loop()` inside `run()` before starting the thread.
- `get_settings()` is `@lru_cache` — new settings apply on fresh start only (consistent with all existing settings).

## Verification (end-to-end)

**A. Flags OFF (regression gate):** fresh base install (no optional groups). App boots; `plugins_discovered`/`startup_complete` logged; no `upstox_/shoonya_/coindcx_/commodity_intel_` lines; no `ingester_module_import_failed` (proves lazy imports). Paper order via `OrderRouter.route(order,"paper")` returns unchanged `PaperExecutionAdapter` fill. `/metrics` renders with new zero-series counters.

**B. "1 file + 0 edits" broker proof:** `git diff --stat` after adding `app/execution/upstox.py` shows **only** that file (no `order_router.py`/engine/registry/loader). Startup logs `adapter_registered adapter_id=upstox`; `mode="upstox"` resolves via `REGISTRY.get_adapter`; flag-off returns graceful `rejected` fill.

**C. Flags ON (per phase):**
- P7 ticks: `TICKS_INGESTED_TOTAL{source="upstox"|"shoonya"}` grows; `redis GET tick:<SYM>` set; `SUBSCRIBE ticks:india` receives JSON.
- P7 exec: `mode="upstox"` → `ExecutionFill(status="submitted")`; bad creds → `rejected`; router untouched.
- P7 Breeze: force Angel options failure → `/api/v1/options/chain` still returns a chain via Breeze; pcr/maxpain/heatmap compute (proves normalization).
- P8: CoinDCX → `ticks:crypto` flow; CoinGecko/CMC → Redis keys `cg:*`/`cmc:*` with TTL; `HTTP_PROVIDER_REQUESTS_TOTAL` increments.
- **P9 (decisive):** `COMMODITY_INTEL_ENABLED=true` → `commodity_signal` logged; Redis `signal:GOLD`/`signal:SILVER` show a **non-zero `india_premium` contributor** (was always 0 — proves the gap closed) with `git diff --stat` showing **0 changes** to `commodity_intelligence_engine.py`.
- P10: `FRED.get_series("us10y")` returns value + Redis `fred:DGS10` TTL≈3600; no-key → `None` + warning.

**D. Static asserts:** grep — no file in `app/ingestion/` or `app/providers/` imports `app.engine`/`app.strategies`/`app.execution` (Law 2); no new `MarketTick(` passes `exchange=`/`ltp=`/OHLC; new ingesters publish only to `MARKET_TICKS` + `CHAN_TICKS_*`.
