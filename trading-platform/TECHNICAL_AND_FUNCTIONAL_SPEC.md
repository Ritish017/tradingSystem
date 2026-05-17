# Trading Platform — Technical & Functional Specification

This document is a **low-level, file-by-file** reference for the entire repository. It is generated from a live scan of every non-empty module and is intended for developers, SREs, and quant engineers who will operate, extend, or audit the platform.

---

## 1. Summary

- **Purpose**: Production-grade algorithmic trading platform for Indian markets (NSE/BSE, NFO/F&O, MCX) and crypto (Binance/OKX). Provides ingestion, signal generation, backtesting, paper/live execution, ML/RL training, monitoring, and governance.
- **Stack**: FastAPI (Python 3.11) backend · Next.js 14 (TypeScript) frontend · PostgreSQL/TimescaleDB · Redis · InfluxDB · Redpanda (Kafka) · MLflow · Grafana · OpenAlgo · Angel One SmartAPI.
- **Entry points**: `backend/app/main.py` (API), `frontend/` (UI), `docker-compose.yml` (infra), `scripts/` (CLI tools).
- **Last updated**: 2026-05-17 (Angel One SmartAPI integration — 6-phase implementation).

---

## 2. Key Capabilities (Functional)

- **Multi-asset coverage**: equities, futures/options (NFO), commodities (MCX), crypto.
- **Strategy types**: rule-based, ML alpha models (LightGBM, LSTM, Transformer), RL agents (PPO, TD3), ~10 strategies total.
- **Execution**: paper and live with Indian brokers (Angel One SmartAPI direct + OpenAlgo facade for Zerodha/Shoonya/Upstox) and crypto via CCXT. Paper trading engine remains fully intact and runs in parallel.
- **Angel One live data**: SmartWebSocketV2 tick stream alongside Binance WebSocket crypto data; both flow into the same `market_ticks` Redpanda topic.
- **Backtesting**: realistic Indian market cost/tax model (STT, exchange charges, GST, SEBI, stamp duty), vectorbt-based.
- **Self-learning**: nightly RL retraining with Sharpe-ratio acceptance gate; strategy weight updates from trade outcomes.
- **Hybrid signal fusion**: 0.4×market + 0.3×news + 0.2×macro + 0.1×social with conflict rejection.
- **Multi-agent intelligence**: 9 specialist agents (news, macro, technical, quant, commodity, crypto, risk, portfolio, execution) with weighted ensemble voting and risk-manager veto.
- **Options analytics**: full option chain with Black-Scholes Greeks, implied volatility (brentq bisection), PCR (OI + volume), max pain, OI heatmap.
- **Risk controls**: hard daily-loss limit, concentration/exposure caps, F&O margin ceiling, circuit breaker on consecutive losses, kill switch.
- **Observability**: Prometheus `/metrics`, Grafana dashboards, MLflow experiment tracking, structlog JSON logging.
- **Persistence**: InfluxDB (ticks/OHLCV), PostgreSQL/TimescaleDB (trades/orders/positions/strategies/candles/option snapshots), Redis (state/pub-sub/signal cache/candle ZSETs), Redpanda (event bus).

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Market Data Sources                                                │
│  Angel One SmartWebSocketV2 · Binance WebSocket · yfinance/CCXT    │
│  macro APIs                                                         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ market_ticks topic (Redpanda)
                            │ Redis pub/sub: ticks:india / ticks:crypto
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TickAggregator (engine/tick_aggregator.py)                         │
│  OHLC candle building 1m/5m/15m/1h → Redis ZSET + pub/sub          │
│  Mark-to-market unrealized PnL updates on STATE.positions           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────────────┐
│  Hybrid Engine (7 microservices via docker-compose)                 │
│  normalization → feature_engineering → llm_agent                   │
│  signal_fusion_engine · commodity_intelligence_engine               │
│  macro_analyst_agent · commodity_analyst_agent                      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ unified_signal topic (Redpanda)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Master Engine (MasterEngineService)                                │
│  SignalAggregator → PositionSizer → RiskGate → OrderRouter          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ExecutionFill
                   ┌────────┼────────┬──────────────┐
                   ▼        ▼        ▼              ▼
             PaperExec  OpenAlgo  AngelOne       CCXT
                            │
                            ▼
              PostgreSQL/TimescaleDB · Redis · Prometheus
                            │
                    FastAPI REST + WebSocket (55 routes)
                            │
                    Next.js 14 Frontend (Zustand stores)
```

---

## 4. Top-Level & Configuration Files

### [pyproject.toml](pyproject.toml)
- Python 3.11–3.12 project, setuptools backend.
- **Runtime deps**: FastAPI, SQLAlchemy, Pydantic, asyncpg, Redis, structlog, ccxt, kiteconnect, pandas, numpy, qlib, vectorbt, quantstats, mlflow, pandas_ta, httpx.
- **Angel One additions**: `smartapi-python>=1.4.3`, `tenacity>=8.5.0,<10.0.0`, `pyotp>=2.9.0,<3.0.0`, `scipy>=1.13.0,<2.0.0`, `aiosqlite>=0.20.0,<1.0.0`.
- **Dev deps**: pytest, pytest-asyncio, mypy, ruff.

### [docker-compose.yml](docker-compose.yml)
- Orchestrates **15+ services**:
  - Infra: PostgreSQL/TimescaleDB (`timescale/timescaledb:latest-pg16`), Redis, InfluxDB, Redpanda, MLflow, Grafana, Prometheus, OpenAlgo.
  - Backend API + Frontend.
  - **Hybrid engine microservices** (7): `market_data_service`, `macro_data_service`, `normalization_service`, `feature_engineering_service`, `llm_agent_service`, `signal_fusion_engine`, `commodity_intelligence_engine`, `macro_analyst_agent`, `commodity_analyst_agent`.
- PostgreSQL mounts `./database/migrations:/docker-entrypoint-initdb.d` to auto-apply TimescaleDB schema on first start.
- Services communicate via **Redpanda topics** and **Redis**.

### [.env](.env)
- Angel One credentials block:
  - `ANGEL_ENABLED=false` — set to `true` to activate live Angel One data + execution.
  - `ANGEL_API_KEY=` — SmartAPI API key.
  - `ANGEL_CLIENT_CODE=` — Angel One client code.
  - `ANGEL_PIN=` — login PIN.
  - `ANGEL_TOTP_SECRET=` — base32 TOTP secret for authenticator-based OTP.
- All credentials come from environment variables only; never hardcoded.

### [database/migrations/001_angelone_schema.sql](database/migrations/001_angelone_schema.sql)
- TimescaleDB schema auto-applied on Postgres container first start.
- **Tables**: `instrument_cache`, `candles` (hypertable, 7-day chunks, 2yr retention), `option_snapshots` (hypertable, 1-day chunks), `orders`, `trades`, `portfolio_snapshots`, `ticks` (hypertable, 1hr chunks, 7-day retention).
- **Continuous aggregate**: `candles_daily` materialised view over 1m candles.

### [configs/features/default.yml](configs/features/default.yml)
- **Indicator config**: `rule_based` (rsi_14, ema_20, ema_50, supertrend_10_3), `ml_alpha`, `rl_agents`.
- **Risk limits**: `max_daily_loss_pct: 0.02`, `max_position_concentration_pct: 0.20`, `max_gross_exposure_pct: 1.0`, `max_fo_margin_utilisation_pct: 0.60`, `circuit_breaker_losses: 3`.
- **Learning**: `retrain_schedule_utc: "02:00"`, `replay_buffer_lookback_days: 30`, `deploy_sharpe_threshold_ratio: 0.9`.

---

## 5. Backend: Core Layer

### [backend/app/main.py](backend/app/main.py)
- FastAPI app (`title="Trading Platform API"`, `version="0.1.0"`).
- **Routers mounted** (original): `strategies`, `orders`, `positions`, `pnl`, `backtest`, `system`, `risk`, `learning`, `intelligence`, `commodities`, `hybrid_signals`, `ws_live`.
- **New routers added** (Angel One): `market` (`/api/v1/market`), `options_chain` (`/api/v1/options`), `portfolio_live` (`/api/v1/portfolio`), `orders_v1` (`/api/v1/orders`), `ws_angelone` (no prefix — WebSocket routes include full path).
- **Startup event** (`startup()`):
  - `ENGINE.register_default_strategies()`.
  - `asyncio.create_task(start_unified_signal_consumer())`.
  - `asyncio.create_task(TICK_AGGREGATOR.run())` — always started.
  - If `ANGEL_ENABLED=true` and `ANGEL_API_KEY` set: auto-login (`ANGEL_SESSION.ensure_active()`), download instruments (`INSTRUMENTS.download_and_cache()`), start order stream (`ANGEL_ORDER_STREAM.start()`), start tick ingestion (`ANGEL_INGESTION.run()` as background task).
- **Endpoints** (global): `GET /`, `GET /healthz`, `GET /metrics`.
- Total routes: **55**.

### [backend/app/core/config.py](backend/app/core/config.py)
- `Settings` (Pydantic `BaseSettings`), environment-driven.
- **Angel One settings block added**:
  - `angel_api_key`, `angel_client_code`, `angel_pin`, `angel_totp_secret` — credentials from env.
  - `angel_ws_url` — default `wss://smartapisocket.angelone.in/smart-stream`.
  - `angel_order_ws_url` — default `wss://smartapisocket.angelone.in/order-update`.
  - `angel_enabled: bool` — feature gate (default `False`).
- Singleton via `@lru_cache` on `get_settings()`.

### [backend/app/core/db.py](backend/app/core/db.py)
- `HealthChecker` with async methods: `check_postgres`, `check_redis`, `check_influxdb`, `check_redpanda`, `check_mlflow`, `check_grafana`, `check_openalgo`.

### [backend/app/core/types.py](backend/app/core/types.py)
- **Frozen dataclasses**: `MarketTick`, `Signal`, `AggregatedSignal`, `OrderRequest`, `ExecutionFill`, `RiskDecision`.

### [backend/app/core/state.py](backend/app/core/state.py)
- `EngineState` singleton `STATE` — tracks positions, orders, fills, signals, strategies.
- `PositionState.unrealized_pnl` updated in real-time by `TickAggregator._update_state_mtm()`.

### [backend/app/core/backtester.py](backend/app/core/backtester.py)
- `Backtester.run()` — vectorbt-based with realistic Indian market cost model.

### [backend/app/core/costs.py](backend/app/core/costs.py)
- `calculate_indian_equity_cost()` — Zerodha model with STT, GST, SEBI, stamp duty.

---

## 6. Backend: Angel One Service Layer

All services under `backend/app/services/angelone/`. All are async, use httpx, wrap calls with tenacity retry, and log with structlog.

### [backend/app/services/angelone/session.py](backend/app/services/angelone/session.py)
- `AngelOneSession` — singleton JWT session manager.
- **Login**: POST `https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword` with clientcode + PIN + TOTP (via pyotp).
- **Refresh**: POST `.../jwt/v1/generateTokens` with refreshToken. Triggered 10 minutes before expiry. Falls back to re-login on refresh failure.
- **Headers**: `X-PrivateKey` (API key), `X-ClientLocalIP`, `X-ClientPublicIP`, `X-MACAddress`, `X-UserType=USER`, `X-SourceID=WEB`.
- **Retry**: 3 attempts with exponential backoff on login; 2 attempts on refresh.
- `ANGEL_SESSION` singleton.

### [backend/app/services/angelone/instruments.py](backend/app/services/angelone/instruments.py)
- `InstrumentService` — downloads and caches the full Angel One instrument master.
- **Download URL**: `https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json`.
- **SQLite cache**: `/tmp/angelone_instruments.db` — `instruments` table with token, symbol, name, expiry, strike, lotsize, instrumenttype, exch_seg, tick_size.
- **Redis cache**: `inst:sym:{exchange}:{symbol}` → token (TTL 86400s); `inst:tok:{exchange}:{token}` → JSON record (TTL 86400s).
- **Exchange type map**: NSE=1, NFO=2, BSE=3, BFO=4, MCX=5, NCDEX=7, CDS=13.
- Methods: `download_and_cache()`, `ensure_loaded()`, `symbol_to_token()`, `token_to_info()`, `search()`, `exchange_type()`.
- `INSTRUMENTS` singleton.

### [backend/app/services/angelone/marketdata.py](backend/app/services/angelone/marketdata.py)
- `MarketDataService` — REST market data (LTP, full quote, OHLC, depth).
- **Endpoint**: POST `/rest/secure/angelbroking/market/v1/quote/` with mode `LTP`/`FULL`/`OHLC`.
- **Price conversion**: `_paise_to_rupees()` — Angel One returns prices multiplied by 100.
- **Redis caching**: `ltp:{exchange}:{token}` (TTL 1s), `quote:{exchange}:{token}` (TTL 5s).
- `MARKET_DATA` singleton.

### [backend/app/services/angelone/websocket.py](backend/app/services/angelone/websocket.py)
- `AngelOneWebSocket` — bridges SmartWebSocketV2 (threaded callbacks) to asyncio.
- **Pattern**: SmartWebSocketV2 runs in a daemon thread (`angel-ws`). Callbacks use `asyncio.run_coroutine_threadsafe()` to enqueue messages into `asyncio.Queue(maxsize=50_000)`. Queue drops oldest on full.
- **Subscription modes**: `_MODE_LTP=1`, `_MODE_QUOTE=2`, `_MODE_SNAP=3`.
- **Exchange types**: NSE=1, NFO=2, BSE=3, BFO=4, MCX=5.
- Methods: `add_subscription()` (pre-start), `start()` (launches thread), `stream()` (async generator), `subscribe()` / `unsubscribe()` (dynamic, live).
- `ANGEL_WS` singleton.

### [backend/app/services/angelone/orderstream.py](backend/app/services/angelone/orderstream.py)
- `AngelOneOrderStream` — SmartWebSocketOrderUpdate in daemon thread (`angel-order-ws`).
- `asyncio.Queue(maxsize=5_000)` for order update events.
- `add_callback()` registers async handlers; `_drain()` task dispatches to all callbacks.
- Callbacks publish to Redis `order_updates` channel for WebSocket relay.
- `ANGEL_ORDER_STREAM` singleton.

### [backend/app/services/angelone/orders.py](backend/app/services/angelone/orders.py)
- Module-level async functions (no class wrapper):
  - `place_order()` — POST `/rest/secure/angelbroking/order/v1/placeOrder`.
  - `modify_order()` — POST `.../modifyOrder`.
  - `cancel_order()` — POST `.../cancelOrder`.
  - `get_order_book()` — GET `.../getOrderBook`.
  - `get_trade_book()` — GET `.../getTradeBook`.
- All calls go through `ANGEL_SESSION.get_headers()` for auth.

### [backend/app/services/angelone/portfolio.py](backend/app/services/angelone/portfolio.py)
- `PortfolioService`:
  - `get_holdings()` — GET `/rest/secure/angelbroking/portfolio/v1/getAllHolding`.
  - `get_positions()` — GET `.../order/v1/getPosition`.
  - `get_funds()` — GET `.../user/v1/getRMS`.
  - `get_holdings_with_ltp()` — enriches each holding with live LTP from `MARKET_DATA`.
  - `compute_pnl()` — aggregates realized + unrealized PnL across holdings + positions.
- `PORTFOLIO` singleton.

### [backend/app/services/angelone/historical.py](backend/app/services/angelone/historical.py)
- `HistoricalService` — fetches OHLCV candles via Angel One historical API v3.
- **Endpoint**: POST `/rest/secure/angelbroking/historical/v3/getCandleData`.
- **Intervals**: `ONE_MINUTE`, `THREE_MINUTE`, `FIVE_MINUTE`, `TEN_MINUTE`, `FIFTEEN_MINUTE`, `THIRTY_MINUTE`, `ONE_HOUR`, `ONE_DAY`.
- **Redis ZSET cache**: TTL 60s for 1m, 300s for other intervals.
- `backfill()` — chunks requests into 59-day windows to respect API limits.
- **Retry**: 3 attempts with exponential backoff on `httpx.HTTPError`.
- `HISTORICAL` singleton.

### [backend/app/services/angelone/options.py](backend/app/services/angelone/options.py)
- `OptionChainService`:
  - `get_option_chain(symbol, expiry, strike=0, enrich_greeks=True)` — POST `/rest/secure/angelbroking/market/v1/optionChain`. Optionally calls `enrich_chain_with_greeks()`.
  - `get_expiry_list(symbol, exchange)` — returns available expiry dates.
  - 60s Redis cache per (symbol, expiry, strike) key.
- `OPTION_CHAIN` singleton.

---

## 7. Backend: Options Analytics Engine

All under `backend/app/services/options/`. Pure Python math — no external dependencies for BS pricing.

### [backend/app/services/options/greeks.py](backend/app/services/options/greeks.py)
- `black_scholes_price(S, K, T, r, sigma, option_type)` — BS option price. T in years, r and sigma as decimals. Returns intrinsic value if T≤0 or sigma≤0.
- `compute_greeks(S, K, T, r, sigma, option_type)` — returns dict: `delta, gamma, theta, vega, rho`.
  - Theta divided by 365 (daily decay). Vega divided by 100 (per 1% vol move). Rho divided by 100 (per 1% rate move).
- `_norm_pdf`, `_norm_cdf` implemented via `math.erf` — no scipy required for Greeks.

### [backend/app/services/options/iv.py](backend/app/services/options/iv.py)
- `implied_volatility(market_price, S, K, T, r, option_type)` — IV via brentq bisection.
- Search bracket: `[1e-4, 20.0]` (1 bp to 2000% vol). Max 200 iterations, tolerance 1e-6.
- Returns `None` if no bracket solution (e.g. deep ITM/OTM with zero time value).

### [backend/app/services/options/chain.py](backend/app/services/options/chain.py)
- `enrich_chain_with_greeks(chain_data)` — processes Angel One `optionChain` response.
- Computes IV then Greeks for each CE/PE row; attaches to chain dict in-place.
- `_days_to_expiry()` parses `DDMMMYYYY` and other Angel One date formats.
- `_RISK_FREE_RATE = 0.065` (RBI repo rate).

### [backend/app/services/options/pcr.py](backend/app/services/options/pcr.py)
- `compute_pcr(chain_rows)` — returns `pcr_oi`, `pcr_volume`, totals, `sentiment`.
- Sentiment: `bullish` if `pcr_oi > 1.2`, `bearish` if `< 0.7`, else `neutral`.

### [backend/app/services/options/maxpain.py](backend/app/services/options/maxpain.py)
- `compute_max_pain(chain_rows)` — brute force over all strikes.
- At each trial strike, sums total payout to option buyers across all CE/PE.
- Returns `max_pain_strike`, `min_total_pain`, `pain_values` list.

### [backend/app/services/options/heatmap.py](backend/app/services/options/heatmap.py)
- `build_oi_heatmap(chain_rows)` — OI heatmap with normalised heat values `[0, 1]`.
- `call_heat = call_oi / max_call_oi`, `put_heat = put_oi / max_put_oi`.
- Rows sorted by strike descending.

---

## 8. Backend: Ingestion Layer

### [backend/app/ingestion/angelone_ws.py](backend/app/ingestion/angelone_ws.py)
- `AngelOneTickIngestionService` — consumes ticks from `ANGEL_WS.stream()` and fans out to:
  1. Redpanda `market_ticks` topic (via `TickPublisher`, alongside Binance).
  2. Redis pub/sub channel `ticks:india`.
  3. Redis cache key `tick:{symbol}` (TTL 60s).
- **Default NSE tokens**: SBIN(3045), INFY(1594), RELIANCE(2885), TCS(11536), BAJFINANCE(5633), NIFTY50(99926004), BANKNIFTY(99926009).
- **`_parse_angel_tick()`**: handles paise conversion — divides by 100 only if value is `int` and `> 10000`; parses `exchange_timestamp` (ms epoch) or falls back to `datetime.now(UTC)`.
- `subscribe_tokens(exchange, tokens)` — dynamically adds subscriptions at runtime.
- `ANGEL_INGESTION` singleton.

### [backend/app/ingestion/market_data_service.py](backend/app/ingestion/market_data_service.py)
- Background service polling on 60s interval.
- **Sources**: yfinance (free) + CCXT Binance.
- **Symbols**: India equities (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, NIFTY50, BANKNIFTY), crypto (BTC/USDT, ETH/USDT), commodities (gold, silver, crude).
- Publishes `MarketTick` to `market_ticks` Redpanda topic.

### [backend/app/ingestion/crypto_ccxt.py](backend/app/ingestion/crypto_ccxt.py)
- `CryptoTickIngestionService` — Binance WebSocket ingestion.
- Publishes to `ticks:crypto` Redis pub/sub.

### Other ingestion modules:
- `india_kite_ws.py` — Kite WebSocket live tick ingestion.
- `macro_data_service.py` — Macro data (RBI/Fed/CPI/GDP) fetching.
- `publisher.py` — `TickPublisher` abstraction over Redpanda + InfluxDB.
- `free_data_provider.py` — yfinance-based free data fallback.

---

## 9. Backend: Engine Layer

### [backend/app/engine/tick_aggregator.py](backend/app/engine/tick_aggregator.py)
- `TickAggregator` — always-running background task that builds OHLC candles from live ticks.
- **Consumption**: tries Redpanda `market_ticks` topic first; falls back to Redis pub/sub (`ticks:india`, `ticks:crypto`) if Redpanda unavailable.
- **Candle building**: `_TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}`. `_bar_start()` aligns timestamp to interval boundary.
- **`CandleBar` dataclass**: tracks `open, high, low, close, volume, ticks`. `update()` updates high/low/close/volume on each tick.
- **Closed bar emission**: stores in Redis ZSET `candles:{symbol}:{timeframe}` (last 500, TTL 7 days); publishes to Redis pub/sub `candles:{timeframe}` for live chart WebSocket clients.
- **Mark-to-market**: `_update_state_mtm()` updates `STATE.positions[symbol].unrealized_pnl` on every tick.
- `get_candles(symbol, timeframe, limit)` — reads from Redis ZSET for API responses.
- `TICK_AGGREGATOR` singleton (started in `main.py` startup).

### [backend/app/engine/service.py](backend/app/engine/service.py)
- `MasterEngineService` — central orchestrator.
- `register_default_strategies()` — 10 defaults across `rule_based`, `ml_alpha`, `rl_agent` strategy types.
- `submit_aggregated_signal()` — full pipeline: aggregate → size → risk-gate → route order → update position.

### [backend/app/engine/order_router.py](backend/app/engine/order_router.py)
- `OrderRouter.route(order_request) → ExecutionFill`.
- **Modes**: `paper` → `PaperExecutionAdapter`, `india` → `IndiaOpenAlgoAdapter`, `crypto` → `CryptoCCXTAdapter`, **`angelone`** → `AngelOneExecutionAdapter` (new).

### [backend/app/engine/signal_aggregator.py](backend/app/engine/signal_aggregator.py)
- Weighted voting on side using `STATE.strategies[name].current_weight`.

### [backend/app/engine/risk_gate.py](backend/app/engine/risk_gate.py)
- Five checks: daily loss limit, position concentration, gross exposure, F&O margin utilisation, circuit breaker.

### [backend/app/engine/position_sizer.py](backend/app/engine/position_sizer.py)
- `per_trade_risk_budget = capital × 0.01`, `target_weight = min(strength × confidence, 0.20)`.

---

## 10. Backend: Execution Adapters

### [backend/app/execution/angelone.py](backend/app/execution/angelone.py)
- `AngelOneExecutionAdapter` — routes live orders through Angel One SmartAPI.
- Resolves symbol → token via `INSTRUMENTS.symbol_to_token()`.
- Auto-detects NFO exchange for symbols ending in `FUT`, `CE`, or `PE`.
- On `token is None`: logs error, returns `ExecutionFill(status="rejected")` — no exception propagated.
- On success: returns `ExecutionFill(status="submitted")` with Angel One's `order_id`.

### [backend/app/execution/paper.py](backend/app/execution/paper.py)
- `PaperExecutionAdapter` — stochastic slippage 1–8 bps, 100% fill for qty≤10, 60% otherwise.

### [backend/app/execution/india_openalgo.py](backend/app/execution/india_openalgo.py)
- `IndiaOpenAlgoAdapter` — POST to OpenAlgo REST API.

### [backend/app/execution/crypto_ccxt.py](backend/app/execution/crypto_ccxt.py)
- `CryptoCCXTAdapter` — CCXT-based crypto order placement.

---

## 11. Backend: API Routes

### Original routes (unchanged)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root health message |
| GET | `/healthz` | Component health (Postgres, Redis, InfluxDB, Redpanda, MLflow, Grafana, OpenAlgo) |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/strategies` | List all strategies |
| POST | `/api/strategies/{name}/status` | Update strategy status |
| GET | `/api/orders` | List orders |
| POST | `/api/orders` | Submit manual order |
| GET | `/api/positions` | Current positions |
| GET | `/api/pnl` | PnL summary |
| POST | `/api/backtest/run` | Trigger backtest |
| GET | `/api/risk` | Risk snapshot |
| POST | `/api/risk/kill-switch` | Emergency halt |
| POST | `/api/risk/resume` | Resume trading |
| POST | `/api/system/halt` | Manual halt |
| POST | `/api/system/resume` | Manual resume |
| GET | `/api/learning/runs` | Retraining run history |
| GET | `/api/intelligence/regime` | Market regime detection |
| GET | `/api/intelligence/cross-market` | Cross-asset correlation |
| POST | `/api/intelligence/analyze` | Run multi-agent orchestration |
| GET | `/api/intelligence/agents` | List available agents |
| GET | `/api/commodities/gold-silver` | Gold/silver snapshot |
| GET | `/api/commodities/mcx` | MCX contracts |
| GET | `/api/commodities/spread` | India premium vs COMEX |
| GET | `/api/hybrid/signals` | Latest unified signals (all assets) |
| GET | `/api/hybrid/signals/{asset}` | Single-asset unified signal |
| GET | `/api/hybrid/health` | Signal freshness health check |
| WS | `/ws/live` | 1-second live tick (PnL, positions, orders, halt status) |

### New Angel One routes

#### [backend/app/api/routes/market.py](backend/app/api/routes/market.py) — prefix `/api/v1/market`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/market/quote` | Full quote (LTP, OHLC, depth, vol) for a symbol |
| GET | `/api/v1/market/ltp` | Last traded price only (1s Redis cache) |
| GET | `/api/v1/market/depth` | Market depth (5-level bid/ask ladder) |
| GET | `/api/v1/market/candles` | OHLC candles — live aggregator first, falls back to Angel One historical API |
| GET | `/api/v1/market/ohlc` | Current day OHLC snapshot |
| GET | `/api/v1/market/search` | Instrument search (symbol or name, optional exchange filter) |

#### [backend/app/api/routes/options_chain.py](backend/app/api/routes/options_chain.py) — prefix `/api/v1/options`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/options/chain` | Full option chain with Greeks, PCR, max pain, OI heatmap |
| GET | `/api/v1/options/greeks` | Greeks for arbitrary (spot, strike, T, IV, type) inputs |
| GET | `/api/v1/options/expiries` | Available expiry dates for a symbol |
| GET | `/api/v1/options/pcr` | Put-Call Ratio (OI + volume based) |
| GET | `/api/v1/options/maxpain` | Max pain strike calculation |
| GET | `/api/v1/options/heatmap` | OI heatmap data (normalised call/put heat) |

#### [backend/app/api/routes/portfolio_live.py](backend/app/api/routes/portfolio_live.py) — prefix `/api/v1/portfolio`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/portfolio/holdings` | Holdings enriched with live LTP |
| GET | `/api/v1/portfolio/positions` | Live intraday positions |
| GET | `/api/v1/portfolio/pnl` | Aggregated PnL + available cash + margin |
| GET | `/api/v1/portfolio/funds` | Funds / RMS (margin available, used, net) |

#### [backend/app/api/routes/orders_v1.py](backend/app/api/routes/orders_v1.py) — prefix `/api/v1/orders`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/orders/place` | Place a new order (full Angel One params: variety, producttype, etc.) |
| PUT | `/api/v1/orders/modify` | Modify an existing order |
| DELETE | `/api/v1/orders/cancel` | Cancel an order by ID |
| GET | `/api/v1/orders/book` | Full order book from Angel One |
| GET | `/api/v1/orders/tradebook` | Trade book (executed fills) |

- `PlaceOrderRequest` Pydantic model with full fields: `tradingsymbol, symboltoken, transactiontype, exchange, ordertype, producttype, variety, duration, quantity, price, triggerprice, squareoff, stoploss, trailingStopLoss`.

#### [backend/app/api/routes/ws_angelone.py](backend/app/api/routes/ws_angelone.py) — WebSocket routes

| Method | Path | Description |
|--------|------|-------------|
| WS | `/api/v1/ws/ticks` | Live market ticks (Redis pub/sub relay). Optional `?symbols=A,B` filter. |
| WS | `/api/v1/ws/orders` | Live order update events (Redis `order_updates` channel). |
| WS | `/api/v1/ws/candles` | Completed OHLC bars. `?timeframe=1m\|5m\|15m\|1h`. |

---

## 12. Backend: Hybrid Engine

### [backend/app/hybrid_engine/kafka_utils.py](backend/app/hybrid_engine/kafka_utils.py)
- `ensure_topics()`, `publish()`, `consume()` — Redpanda REST Proxy utilities.
- **Topics**: `market_ticks`, `raw_news`, `macro_data`, `normalized_data`, `features`, `news_signals`, `unified_signal`.

### [backend/app/hybrid_engine/fusion/signal_fusion_engine.py](backend/app/hybrid_engine/fusion/signal_fusion_engine.py)
- **Fusion formula**: `0.4×market + 0.3×news + 0.2×macro + 0.1×social`.
- **Conflict rejection**: `|market_score − news_score| > 0.5` → HOLD.

---

## 13. Backend: Intelligence Layer

### [backend/app/intelligence/orchestrator.py](backend/app/intelligence/orchestrator.py)
- `MultiAgentOrchestrator` — 9 agents, weighted ensemble, risk-manager veto at `ensemble_risk > 0.75`.
- **Agent weights**: news 0.15, macro 0.20, technical 0.15, quant 0.10, commodity 0.10, crypto 0.08, risk 0.12, portfolio 0.07, execution 0.03.

---

## 14. Backend: Tests

### Unit tests:
- `test_healthz_schema.py`, `test_risk_gate.py`, `test_order_state_machine.py`, `test_backtester.py`, `test_crypto_ingestion.py`, `test_features_pipeline.py`, `test_india_equities_ingestion.py`, `test_kite_ingestion.py`.

### Strategy tests:
- `test_strategy_signals.py`.

### Integration tests:
- `test_end_to_end.py` — full pipeline from tick ingestion to execution fill.

---

## 15. Frontend

### [frontend/package.json](frontend/package.json)
- **Runtime**: Next.js 14.2.5, React 18.3.1.
- **Key deps**: `lightweight-charts 4.2.0` (TradingView-style charting), **`zustand ^4.5.4`** (state management — added).
- **Dev deps**: TypeScript 5.5.4, ESLint 8.57.0, Tailwind 3.4.7.

### [frontend/app/(dashboard)/layout.tsx](frontend/app/(dashboard)/layout.tsx)
- Navigation now includes **15 items** with 4 new routes: `/market`, `/trading`, `/options`, `/portfolio`.
- Full list: Dashboard, Market, Trading, Options, Portfolio, Positions, Strategies, Risk, Backtest, Learning, Intelligence, Macro, Commodities, Gold & Silver, Crypto.

### [frontend/lib/ws.ts](frontend/lib/ws.ts)
- `connectLiveWs(path)` — WebSocket factory using `NEXT_PUBLIC_WS_BASE_URL` env var (default `ws://localhost:8000`).

### [frontend/app/api/fastapi/[...path]/route.ts](frontend/app/api/fastapi/%5B...path%5D/route.ts)
- Next.js catch-all API proxy to FastAPI backend (avoids CORS in development).

---

## 16. Frontend: Zustand Stores

All stores under `frontend/store/`. Each exports a typed Zustand store hook.

### [frontend/store/marketSlice.ts](frontend/store/marketSlice.ts)
- `useMarketStore` — ticks (symbol → price), quotes (symbol → full quote), candles (symbol+tf → OHLCV array), watchlist (symbol set).
- Actions: `setTick`, `setQuote`, `setCandles`, `addToWatchlist`, `removeFromWatchlist`.

### [frontend/store/optionsSlice.ts](frontend/store/optionsSlice.ts)
- `useOptionsStore` — chain (expiry → row array), pcr, maxPain, expiries list, selected symbol/expiry.
- Actions: `setChain`, `setPcr`, `setMaxPain`, `setExpiries`, `setSelected`.

### [frontend/store/portfolioSlice.ts](frontend/store/portfolioSlice.ts)
- `usePortfolioStore` — holdings array, positions array, pnl summary object, funds object.
- Actions: `setHoldings`, `setPositions`, `setPnl`, `setFunds`.

### [frontend/store/ordersSlice.ts](frontend/store/ordersSlice.ts)
- `useOrdersStore` — orderBook array, tradeBook array, order form state.
- Actions: `setOrderBook`, `setTradeBook`, `setFormField`, `resetForm`.

---

## 17. Frontend: Components

All components under `frontend/components/`. All are `"use client"` React components.

### [frontend/components/LiveQuoteBar.tsx](frontend/components/LiveQuoteBar.tsx)
- Top ticker strip — connects to `/api/v1/ws/ticks` WebSocket.
- Shows LTP, change, change% for each symbol in watchlist.
- Reconnects automatically on WebSocket close.

### [frontend/components/TradingViewChart.tsx](frontend/components/TradingViewChart.tsx)
- lightweight-charts 4.2.0 candlestick chart with dark theme.
- Connects to `/api/v1/ws/candles?timeframe=X` WebSocket for live bar updates.
- Loads historical candles from `/api/v1/market/candles` on mount.
- Supports timeframe selector (1m / 5m / 15m / 1h).

### [frontend/components/MarketDepth.tsx](frontend/components/MarketDepth.tsx)
- 5-level bid/ask ladder with proportional OI bars.
- Polls `/api/v1/market/depth` every 1 second.
- Shows buy qty, price, sell qty with colour-coded background bars.

### [frontend/components/OptionChain.tsx](frontend/components/OptionChain.tsx)
- Full option chain table: CE side | Strike | PE side.
- Columns: OI, OI change, IV, delta, gamma, theta, vega, LTP, bid, ask.
- Highlights max pain strike, shows PCR badge.
- Fetches from `/api/v1/options/chain`.

### [frontend/components/PortfolioPanel.tsx](frontend/components/PortfolioPanel.tsx)
- Tabbed panel: Holdings | Positions | PnL.
- Holdings table with LTP-enriched market value and unrealized PnL.
- PnL summary with available cash and used margin.
- Refreshes every 15 seconds from `/api/v1/portfolio/` endpoints.

### [frontend/components/OrderPanel.tsx](frontend/components/OrderPanel.tsx)
- Tabbed panel: Place Order | Order Book | Trade Book.
- Order form: symbol, exchange, type, product type, qty, price, trigger price.
- Connects to `/api/v1/ws/orders` WebSocket for live order status updates.
- Order book and trade book fetched from `/api/v1/orders/book` and `/api/v1/orders/tradebook`.

### [frontend/components/FuturesDashboard.tsx](frontend/components/FuturesDashboard.tsx)
- Futures quotes panel for NSE/NFO instruments.
- Shows LTP, OI, volume, OHLC for configured futures symbols.
- Refreshes every 5 seconds.

---

## 18. Frontend: Pages

### [frontend/app/(dashboard)/market/page.tsx](frontend/app/(dashboard)/market/page.tsx)
- Market overview: `LiveQuoteBar` + `TradingViewChart` + `MarketDepth` for selected symbol.
- Symbol search via `/api/v1/market/search`.

### [frontend/app/(dashboard)/trading/page.tsx](frontend/app/(dashboard)/trading/page.tsx)
- Trading terminal: `TradingViewChart` + `OrderPanel` + `FuturesDashboard`.

### [frontend/app/(dashboard)/options/page.tsx](frontend/app/(dashboard)/options/page.tsx)
- Options trading: expiry selector + `OptionChain` + PCR badge + max pain indicator.

### [frontend/app/(dashboard)/portfolio/page.tsx](frontend/app/(dashboard)/portfolio/page.tsx)
- Portfolio overview: `PortfolioPanel` + PnL chart + funds summary.

---

## 19. Database Schema (TimescaleDB)

### [database/migrations/001_angelone_schema.sql](database/migrations/001_angelone_schema.sql)

| Table | Type | Key Info |
|-------|------|----------|
| `instrument_cache` | Regular | PK (token, exchange); indexed by symbol+exchange, expiry |
| `candles` | Hypertable | PK (symbol, timeframe, ts); 7-day chunks; 2yr retention; continuous aggregate `candles_daily` |
| `option_snapshots` | Hypertable | PK (id); 1-day chunks; indexed by symbol+expiry+strike+type+ts |
| `orders` | Regular | PK (order_id); indexed by symbol+ts, status |
| `trades` | Regular | PK (trade_id); FK → orders |
| `portfolio_snapshots` | Regular | Daily snapshots; UNIQUE (snapshot_date, symbol, exchange) |
| `ticks` | Hypertable | 1hr chunks; 7-day retention |

---

## 20. Data Flow (Detailed)

1. **Ingestion (India)**: `AngelOneWebSocket` → `AngelOneTickIngestionService` → Redpanda `market_ticks` + Redis `ticks:india` + `tick:{symbol}`.
2. **Ingestion (Crypto)**: Binance WebSocket → `CryptoTickIngestionService` → Redpanda `market_ticks` + Redis `ticks:crypto`.
3. **Ingestion (Free)**: yfinance/CCXT → `market_data_service` → Redpanda `market_ticks` (60s poll).
4. **Tick Aggregation**: `TickAggregator` consumes `market_ticks` (Redpanda) or Redis pub/sub → builds OHLC bars → Redis ZSET + `candles:{tf}` pub/sub + `STATE.positions` unrealized PnL.
5. **Normalization + Features**: `normalization_service` → `feature_engineering_service` → `features` topic + Redis cache.
6. **News/Macro**: `llm_agent_service`/`macro_analyst_agent` → `news_signals` topic + Redis macro cache.
7. **Signal fusion**: `signal_fusion_engine` fuses features + news + macro → `unified_signal` topic + Redis cache.
8. **Commodity signals**: `commodity_intelligence_engine`/`commodity_analyst_agent` → `unified_signal` for GOLD/SILVER.
9. **Master engine**: `start_unified_signal_consumer()` polls `unified_signal` → `MasterEngineService`: aggregate → size → risk-gate → route order (paper / angelone / openalgo / ccxt).
10. **Order updates**: Angel One order stream → `ANGEL_ORDER_STREAM` → Redis `order_updates` → `/api/v1/ws/orders` WebSocket → frontend `OrderPanel`.
11. **Live charts**: `/api/v1/ws/candles` subscribers receive closed bars from `TickAggregator` → `TradingViewChart` updates in real-time.
12. **Learning feedback**: `TradeOutcomeLogger` → `StrategyScorer.update_weights()` (online) + `RetrainingJob.run_nightly()` (nightly RL).
13. **Observability**: Prometheus `/metrics`, Grafana dashboards, MLflow experiment tracking, structlog JSON.

---

## 21. Configuration & Secrets

- **Env file**: `.env`.
- **Angel One credentials**: `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET` — all from environment only, never logged or exposed.
- **Enable live trading**: set `ANGEL_ENABLED=true` in `.env`.
- **Feature/risk config**: `configs/features/default.yml`.
- **Production secrets**: Vault / cloud secrets manager.

---

## 22. Running Locally

```bash
# 1. Environment
cp .env.example .env
# Edit .env with your API keys
# For Angel One live data: fill ANGEL_API_KEY, ANGEL_CLIENT_CODE, ANGEL_PIN, ANGEL_TOTP_SECRET
# Set ANGEL_ENABLED=true to activate

# 2. Infrastructure (TimescaleDB schema auto-applied on first start)
docker-compose up -d postgres redis influxdb redpanda

# 3. Migrations (Alembic)
cd backend && alembic upgrade head

# 4. Backend API
cd backend && pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 5. Frontend
cd frontend && npm install && npm run dev

# 6. Optional: seed data & backtest
python scripts/seed_historical_data.py --symbols RELIANCE --start 2023-01-01 --end 2023-12-31
python scripts/run_backtest.py --strategy supertrend_rsi --symbols RELIANCE --start 2023-01-01 --end 2023-03-01

# 7. Optional: train RL agents
python scripts/train_rl_agent.py
```

---

## 23. Angel One Integration: Activation Checklist

To activate Angel One live data and execution:

1. Fill in `.env`:
   ```
   ANGEL_ENABLED=true
   ANGEL_API_KEY=your-api-key
   ANGEL_CLIENT_CODE=your-client-code
   ANGEL_PIN=your-4-digit-pin
   ANGEL_TOTP_SECRET=your-base32-totp-secret
   ```
2. Restart the backend — on startup it will:
   - Auto-login via TOTP and obtain JWT.
   - Download ~100k instrument records to SQLite + Redis.
   - Start `SmartWebSocketV2` for NSE equity ticks.
   - Start order update stream for real-time order events.
3. Navigate to `/market` to see live ticks and charts.
4. Navigate to `/trading` to place orders.
5. Navigate to `/options` to view option chains.
6. Navigate to `/portfolio` to see holdings and PnL.

To use **paper trading only** (no Angel One), leave `ANGEL_ENABLED=false` — the platform runs fully in paper mode with yfinance data.

---

## 24. Extension Guide

### Adding a strategy
1. Implement under `backend/app/strategies/` extending `BaseStrategy`.
2. Register in `MasterEngineService.register_default_strategies()`.
3. Add unit test under `backend/app/tests/strategies/`.

### Adding a data source
1. Implement connector publishing normalized `MarketTick` to `market_ticks` Redpanda topic and writing to InfluxDB.
2. Publish ticks to a Redis pub/sub channel for WebSocket streaming.
3. Add `CounterMetric` in `backend/app/core/metrics.py`.

### Adding an intelligence agent
1. Extend `BaseAgent` in `backend/app/intelligence/`.
2. Register in `MultiAgentOrchestrator` with a weight (weights must sum to 1.0).
3. Expose via `GET /api/intelligence/agents`.

### Adding an Angel One instrument subscription
```python
from app.ingestion.angelone_ws import ANGEL_INGESTION
# At runtime, after startup:
ANGEL_INGESTION.subscribe_tokens("NFO", ["35004", "35005"])  # NFO tokens
```

---

## 25. API Surface Reference (Full — 55 routes)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root health message |
| GET | `/healthz` | Component health |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/strategies` | List all strategies |
| POST | `/api/strategies/{name}/status` | Update strategy status |
| GET | `/api/orders` | List engine orders |
| POST | `/api/orders` | Submit manual engine order |
| GET | `/api/positions` | Engine positions |
| GET | `/api/pnl` | Engine PnL summary |
| POST | `/api/backtest/run` | Trigger backtest |
| GET | `/api/risk` | Risk snapshot |
| POST | `/api/risk/kill-switch` | Emergency halt |
| POST | `/api/risk/resume` | Resume trading |
| POST | `/api/system/halt` | Manual halt |
| POST | `/api/system/resume` | Manual resume |
| GET | `/api/learning/runs` | Retraining run history |
| GET | `/api/intelligence/regime` | Market regime detection |
| GET | `/api/intelligence/cross-market` | Cross-asset correlation |
| POST | `/api/intelligence/analyze` | Run multi-agent orchestration |
| GET | `/api/intelligence/agents` | List available agents |
| GET | `/api/commodities/gold-silver` | Gold/silver snapshot |
| GET | `/api/commodities/mcx` | MCX contracts |
| GET | `/api/commodities/spread` | India premium vs COMEX |
| GET | `/api/hybrid/signals` | Latest unified signals |
| GET | `/api/hybrid/signals/{asset}` | Single-asset unified signal |
| GET | `/api/hybrid/health` | Signal freshness health |
| WS | `/ws/live` | 1-second engine live tick |
| GET | `/api/v1/market/quote` | Full quote (Angel One) |
| GET | `/api/v1/market/ltp` | LTP (Angel One, 1s cache) |
| GET | `/api/v1/market/depth` | Market depth 5-level |
| GET | `/api/v1/market/candles` | OHLC candles (live + historical) |
| GET | `/api/v1/market/ohlc` | Day OHLC snapshot |
| GET | `/api/v1/market/search` | Instrument search |
| GET | `/api/v1/options/chain` | Full option chain + Greeks + analytics |
| GET | `/api/v1/options/greeks` | Greeks for arbitrary inputs |
| GET | `/api/v1/options/expiries` | Available expiries |
| GET | `/api/v1/options/pcr` | Put-Call Ratio |
| GET | `/api/v1/options/maxpain` | Max pain strike |
| GET | `/api/v1/options/heatmap` | OI heatmap |
| GET | `/api/v1/portfolio/holdings` | Holdings + live LTP |
| GET | `/api/v1/portfolio/positions` | Live positions |
| GET | `/api/v1/portfolio/pnl` | PnL + funds summary |
| GET | `/api/v1/portfolio/funds` | Funds / RMS |
| POST | `/api/v1/orders/place` | Place Angel One order |
| PUT | `/api/v1/orders/modify` | Modify order |
| DELETE | `/api/v1/orders/cancel` | Cancel order |
| GET | `/api/v1/orders/book` | Order book |
| GET | `/api/v1/orders/tradebook` | Trade book |
| WS | `/api/v1/ws/ticks` | Live tick stream (filterable) |
| WS | `/api/v1/ws/orders` | Live order update stream |
| WS | `/api/v1/ws/candles` | Live closed OHLC bars |

---

*Document updated 2026-05-17 — reflects 6-phase Angel One SmartAPI integration (services layer, options analytics, tick aggregation, live execution adapter, 4 new frontend pages, 7 new components, 4 Zustand stores, 28 new API routes, TimescaleDB schema).*
