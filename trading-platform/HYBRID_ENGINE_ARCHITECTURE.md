# 🧠 Hybrid Data Engine — Architecture & Implementation Guide

> **Engineering Design Document**
> Version: 1.0 | Target: Production
> Stack: FastAPI · Redpanda · InfluxDB · PostgreSQL · Redis · Nemotron 120B

---

## 📌 Overview

The Hybrid Data Engine is the **central intelligence layer** sitting between raw market data and the trading engine.

It ingests from three independent source classes, streams everything through Redpanda, processes it through a normalization → feature → AI pipeline, fuses all signals into a single high-confidence output, and delivers that output to the existing trading engine.

```
Raw World
  ├── Market (NSE/BSE/MCX/Crypto)
  ├── Web Intelligence (Scrapling)
  └── Macro (USD, Bonds, Inflation)
          │
          ▼
    Redpanda Topics
          │
          ▼
    Processing Layer
    ├── Normalization
    ├── Feature Engineering
    └── LLM Intelligence (Nemotron 120B)
          │
          ▼
    Signal Fusion Engine
          │
          ▼
    unified_signal  ──►  Trading Engine
```

---

## 🗂️ Folder Structure

All new code lives inside the **existing** project layout. Nothing is moved.

```
trading-platform/
├── backend/app/
│   ├── hybrid_engine/                  ← CORE (already exists, fill it)
│   │   ├── __init__.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── news_analyst.py         ← LLM news agent
│   │   │   ├── macro_analyst.py        ← LLM macro agent
│   │   │   └── commodity_analyst.py    ← Gold/Silver LLM agent
│   │   ├── fusion/
│   │   │   ├── __init__.py
│   │   │   └── signal_fusion_engine.py ← CORE fusion logic
│   │   ├── normalization/
│   │   │   ├── __init__.py
│   │   │   └── normalization_service.py
│   │   └── storage/
│   │       ├── __init__.py
│   │       └── hybrid_store.py         ← InfluxDB + PG + Redis writes
│   │
│   ├── ingestion/
│   │   ├── market_data_service.py      ← NSE/BSE/MCX/Crypto ticks
│   │   └── macro_data_service.py       ← USD/Bonds/Inflation
│   │
│   └── api/routes/
│       └── hybrid_signals.py           ← REST endpoint for trading engine
│
├── services/
│   └── scrapling_intelligence_service/ ← ALREADY EXISTS — extend it
│       ├── sources/
│       │   ├── india.py                ← Moneycontrol, ET, NSE/BSE, RBI/SEBI
│       │   ├── global.py               ← Reuters, Investing.com
│       │   └── social.py               ← Reddit (Twitter/X optional)
│       ├── pipeline.py                 ← Orchestrates scrape → publish
│       ├── service.py                  ← FastAPI app entry
│       └── signal_generator.py         ← Basic keyword/entity extraction
│
├── commodity_intelligence_engine.py    ← Gold/Silver standalone engine
├── docker-compose.yml                  ← Add new services here
└── HYBRID_ENGINE_ARCHITECTURE.md       ← This file
```

---

## ⚡ Redpanda Topics

Redpanda is **already running** in `docker-compose.yml` on port `9092`.

| Topic | Producer | Consumer | Retention |
|---|---|---|---|
| `market_ticks` | market_data_service | normalization_service | 1h |
| `raw_news` | scrapling_intelligence_service | normalization_service, llm_agent | 6h |
| `macro_data` | macro_data_service | normalization_service | 1h |
| `normalized_data` | normalization_service | feature_engineering_service | 30m |
| `features` | feature_engineering_service | signal_fusion_engine | 30m |
| `news_signals` | llm_agent_service | signal_fusion_engine | 1h |
| `unified_signal` | signal_fusion_engine | trading_engine consumer | 15m |

Create all topics on startup via `rpk topic create` or the admin API.

---

## 1️⃣ Data Services Layer

---

### A. `market_data_service.py`

**Location:** `backend/app/ingestion/market_data_service.py`

**Responsibilities:**
- Poll NSE/BSE ticks via `jugaad-data` or broker WebSocket
- Poll MCX commodity prices
- Stream crypto via `ccxt` (Binance, OKX)
- Publish to `market_ticks`

**Tick schema:**
```json
{
  "symbol": "NSE:RELIANCE",
  "price": 2450.5,
  "volume": 120000,
  "timestamp": "2024-01-15T09:15:00Z",
  "source": "market",
  "exchange": "NSE"
}
```

**Key design decisions:**
- Use `asyncio` + `aiokafka` producer
- Broker failover: Zerodha → Shoonya → Upstox (already in `institutional_data_layer.py`)
- Free data fallback: `yfinance` polling when `USE_FREE_DATA=true`
- Deduplicate ticks by `(symbol, timestamp)` using Redis SET with 5s TTL

---

### B. `scrapling_intelligence_service` (CRITICAL)

**Location:** `services/scrapling_intelligence_service/` ← already exists

**Library:** https://github.com/D4Vinci/Scrapling

**Install:**
```bash
pip install scrapling
playwright install chromium
```

**Sources to scrape:**

| Source | URL | Method |
|---|---|---|
| Moneycontrol | moneycontrol.com/news | CSS selectors |
| Economic Times | economictimes.indiatimes.com | CSS selectors |
| NSE Announcements | nseindia.com/companies-listing/corporate-filings-announcements | API endpoint |
| BSE Filings | bseindia.com/corporates/ann.html | API endpoint |
| RBI | rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | CSS selectors |
| SEBI | sebi.gov.in/sebiweb/other/OtherAction.do?doPress=yes | CSS selectors |
| Reuters India | reuters.com/world/india | CSS selectors |
| Investing.com | investing.com/news/commodities-news | CSS selectors |
| Reddit | reddit.com/r/IndiaInvestments + r/stocks | JSON API |

**Pipeline per article:**
```
1. Detect new URL (Redis SET dedup by URL hash)
2. Fetch with Scrapling (StealthyFetcher for JS-heavy sites)
3. Extract: title, body, timestamp, source_url
4. Entity extraction: regex + keyword match against symbol list
5. Publish to raw_news
```

**raw_news schema:**
```json
{
  "id": "sha256-of-url",
  "title": "Reliance Q3 profit rises 12%",
  "body": "...",
  "source": "economic_times",
  "url": "https://...",
  "entities": ["RELIANCE", "NSE"],
  "timestamp": "2024-01-15T08:30:00Z",
  "scraped_at": "2024-01-15T08:31:05Z"
}
```

**Failure handling:**
- Retry 3× with exponential backoff (2s, 4s, 8s)
- On persistent failure: log + skip, do NOT crash service
- Rate limit: 1 request/2s per domain

---

### C. `macro_data_service.py`

**Location:** `backend/app/ingestion/macro_data_service.py`

**Sources (all free):**

| Signal | Source | Library |
|---|---|---|
| USD Index (DXY) | Yahoo Finance | `yfinance` |
| US 10Y Bond Yield | Yahoo Finance `^TNX` | `yfinance` |
| India 10Y Bond | NSE API | `requests` |
| CPI Inflation | FRED API (free) | `requests` |
| S&P 500 | Yahoo Finance `^GSPC` | `yfinance` |
| Nifty 50 | Yahoo Finance `^NSEI` | `yfinance` |
| Gold (USD) | Yahoo Finance `GC=F` | `yfinance` |
| VIX | Yahoo Finance `^VIX` | `yfinance` |

**macro_data schema:**
```json
{
  "dxy": 104.2,
  "us10y": 4.35,
  "vix": 18.5,
  "sp500_change_pct": -0.3,
  "nifty_change_pct": 0.5,
  "gold_usd": 2045.0,
  "timestamp": "2024-01-15T09:00:00Z",
  "source": "macro"
}
```

**Poll interval:** Every 60 seconds (macro data doesn't need sub-second freshness)

---

## 🔄 2️⃣ Processing Layer

---

### A. `normalization_service.py`

**Location:** `backend/app/hybrid_engine/normalization/normalization_service.py`

**Consumes:** `market_ticks`, `raw_news`, `macro_data`
**Produces:** `normalized_data`

**Rules:**
1. All timestamps → UTC ISO 8601
2. Symbol normalization: `RELIANCE` → `NSE:RELIANCE`, `BTC` → `BINANCE:BTCUSDT`
3. Dedup: skip if identical `(symbol, timestamp)` seen in last 5s (Redis)
4. Missing price/volume: discard tick, log warning
5. Price sanity: reject if `|new_price - last_price| / last_price > 0.1` (10% spike filter)

**normalized_data schema:**
```json
{
  "type": "tick|news|macro",
  "symbol": "NSE:RELIANCE",
  "data": { ... },
  "normalized_at": "2024-01-15T09:15:00.123Z"
}
```

---

### B. `feature_engineering_service.py`

**Location:** `backend/app/features/` (already exists — extend it)

**Consumes:** `normalized_data`
**Produces:** `features`

**Market features (per symbol, rolling window):**

| Feature | Window | Library |
|---|---|---|
| RSI | 14 periods | `pandas-ta` |
| EMA | 9, 21, 50 | `pandas-ta` |
| VWAP | Session | manual calc |
| ATR (volatility) | 14 periods | `pandas-ta` |
| Momentum | 10 periods | `pandas-ta` |

**News features:**
- Keyword match score: count of bullish/bearish keywords in title+body
- Entity count: number of known symbols mentioned

**Macro features:**
- Risk-on score: `(sp500_change + nifty_change) / 2 - vix_normalized`
- USD strength: DXY z-score vs 20-day mean

**features schema:**
```json
{
  "symbol": "NSE:RELIANCE",
  "rsi_14": 58.3,
  "ema_9": 2448.0,
  "ema_21": 2430.0,
  "vwap": 2445.5,
  "atr_14": 32.1,
  "momentum_10": 0.023,
  "news_keyword_score": 0.6,
  "macro_risk_on": 0.4,
  "timestamp": "2024-01-15T09:15:00Z"
}
```

---

### C. LLM Intelligence Layer — `news_analyst.py`

**Location:** `backend/app/hybrid_engine/agents/news_analyst.py`

**Model:** Nemotron 120B (via local endpoint or NVIDIA API)
**Endpoint:** `LLM_ENDPOINT` env var (e.g. `http://localhost:8000/v1/chat/completions`)

**Consumes:** `raw_news`
**Produces:** `news_signals`

**⚠️ HARD RULE: LLM MUST NOT generate trade orders. Output is sentiment/classification only.**

**Prompt structure:**
```
System: You are a financial news analyst. Analyze the article and return JSON only.
User: Article: {title}\n{body[:2000]}
      Return: {"asset": str, "sentiment": float[-1,1], "impact": int[0,100],
               "confidence": float[0,1], "time_horizon": "short|medium|long",
               "reasoning": str (max 50 words)}
```

**news_signals schema:**
```json
{
  "asset": "RELIANCE",
  "sentiment": 0.8,
  "impact": 75,
  "confidence": 0.9,
  "time_horizon": "short",
  "reasoning": "Strong Q3 earnings beat consensus by 12%, positive for near-term price.",
  "source_id": "sha256-of-url",
  "analyzed_at": "2024-01-15T08:31:10Z"
}
```

**Failure handling:**
- LLM timeout (>10s): skip article, log, continue
- Invalid JSON response: retry once with stricter prompt, then skip
- LLM down: fallback to keyword-based sentiment from `signal_generator.py`

**Other agents (same pattern):**
- `macro_analyst.py` — analyzes macro_data, outputs macro risk score
- `commodity_analyst.py` — Gold/Silver specific analysis

---

## 🧠 3️⃣ Signal Fusion Engine (CORE)

**Location:** `backend/app/hybrid_engine/fusion/signal_fusion_engine.py`

**Consumes:** `features`, `news_signals`, `macro_data` (via Redpanda)
**Produces:** `unified_signal`

### Fusion Formula

```
final_score = (0.4 × market_signal)
            + (0.3 × news_signal)
            + (0.2 × macro_signal)
            + (0.1 × social_signal)
```

Where each component is normalized to `[-1.0, 1.0]`.

### Signal Derivation

**market_signal** (from features):
```python
# RSI: overbought/oversold
rsi_signal = (rsi - 50) / 50  # -1 to 1

# Momentum
momentum_signal = clip(momentum_10 * 10, -1, 1)

# EMA trend
ema_signal = 1 if ema_9 > ema_21 > ema_50 else -1 if ema_9 < ema_21 < ema_50 else 0

market_signal = (rsi_signal + momentum_signal + ema_signal) / 3
```

**news_signal** (from news_signals):
```python
# Latest signal for asset, weighted by confidence
news_signal = sentiment × confidence  # already in [-1, 1]
```

**macro_signal** (from macro_data):
```python
macro_signal = macro_risk_on  # computed in feature engineering
```

**social_signal** (from news_signals where source=reddit/twitter):
```python
social_signal = mean(sentiment for social sources)
```

### Validation Rules

```python
MIN_CONFIDENCE = 0.6          # Reject if final confidence < 0.6
MAX_SIGNAL_AGE_SECONDS = 300  # Reject stale signals (>5 min old)
CONFLICT_THRESHOLD = 0.5      # Reject if |market - news| > 0.5 (conflicting)
```

### Action Mapping

```python
if final_score > 0.3 and confidence >= MIN_CONFIDENCE:
    action = "BUY"
elif final_score < -0.3 and confidence >= MIN_CONFIDENCE:
    action = "SELL"
else:
    action = "HOLD"
```

### unified_signal schema

```json
{
  "asset": "NSE:RELIANCE",
  "action": "BUY",
  "final_score": 0.52,
  "confidence": 0.82,
  "contributors": {
    "market": 0.6,
    "news": 0.8,
    "macro": 0.5,
    "social": 0.3
  },
  "weights_used": {
    "market": 0.4,
    "news": 0.3,
    "macro": 0.2,
    "social": 0.1
  },
  "signal_age_seconds": 12,
  "generated_at": "2024-01-15T09:15:12Z"
}
```

---

## 🥇 4️⃣ Commodity Intelligence Engine

**Location:** `backend/app/commodities/commodity_intelligence_engine.py`

**Tracks:**
- Gold spot (India MCX vs global COMEX) — spread analysis
- Silver spot (India MCX vs global)
- USD/INR rate (affects import parity)
- DXY strength (inverse correlation with gold)
- Inflation (CPI) — gold as inflation hedge signal
- Geopolitical risk proxy: VIX + news keyword scan for "war", "sanctions", "conflict"

**Logic:**
```python
gold_bias_score = (
    -0.4 × dxy_zscore          # Strong USD = bearish gold
  +  0.3 × inflation_zscore    # High inflation = bullish gold
  +  0.2 × geopolitical_score  # Risk events = bullish gold
  +  0.1 × india_premium       # India premium > 0 = local demand
)
```

**Output schema:**
```json
{
  "asset": "GOLD",
  "bias": "bullish",
  "confidence": 0.85,
  "drivers": {
    "usd_strength": -0.3,
    "inflation": 0.6,
    "geopolitical": 0.4,
    "india_premium": 0.2
  },
  "mcx_price": 62500,
  "comex_price_inr": 62100,
  "spread_pct": 0.64,
  "generated_at": "2024-01-15T09:00:00Z"
}
```

---

## 🔌 5️⃣ Integration with Trading Engine

### Option A — Redpanda Consumer (recommended)

The existing trading engine subscribes to `unified_signal` topic:

```python
# In backend/app/engine/service.py — add consumer
consumer = AIOKafkaConsumer(
    "unified_signal",
    bootstrap_servers=settings.redpanda_brokers,
    group_id="trading-engine",
    value_deserializer=lambda m: json.loads(m.decode())
)

async for msg in consumer:
    signal = msg.value
    if signal["action"] in ("BUY", "SELL") and signal["confidence"] >= 0.7:
        await engine.process_hybrid_signal(signal)
```

### Option B — REST endpoint

**Location:** `backend/app/api/routes/hybrid_signals.py`

```
GET  /api/hybrid/signals          → latest unified_signal per asset
GET  /api/hybrid/signals/{asset}  → signal history for asset
POST /api/hybrid/signals/consume  → manual trigger (testing)
```

---

## 📦 6️⃣ Storage Layer

| Data | Store | Details |
|---|---|---|
| Raw ticks | InfluxDB `ticks` bucket | Already configured |
| Normalized features | InfluxDB `features` bucket | New bucket |
| News signals | PostgreSQL `news_signals` table | New table |
| Unified signals | PostgreSQL `unified_signals` table | New table |
| LLM analysis cache | Redis (TTL 1h) | Key: `llm:{article_id}` |
| Dedup sets | Redis (TTL 5s) | Key: `dedup:{symbol}:{ts}` |
| Latest signal per asset | Redis (TTL 5m) | Key: `signal:{asset}` |

### PostgreSQL Tables

```sql
-- news_signals
CREATE TABLE news_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(50) NOT NULL,
    sentiment FLOAT NOT NULL,
    impact INT NOT NULL,
    confidence FLOAT NOT NULL,
    time_horizon VARCHAR(10),
    reasoning TEXT,
    source_id VARCHAR(64),
    analyzed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- unified_signals
CREATE TABLE unified_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(50) NOT NULL,
    action VARCHAR(10) NOT NULL,
    final_score FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    contributors JSONB,
    generated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🐳 7️⃣ Docker Compose Additions

Add these services to the existing `docker-compose.yml`:

```yaml
  market_data_service:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.ingestion.market_data_service
    env_file: .env
    depends_on:
      redpanda:
        condition: service_started
      redis:
        condition: service_healthy
    restart: unless-stopped

  macro_data_service:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.ingestion.macro_data_service
    env_file: .env
    depends_on:
      redpanda:
        condition: service_started
    restart: unless-stopped

  normalization_service:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.hybrid_engine.normalization.normalization_service
    env_file: .env
    depends_on:
      redpanda:
        condition: service_started
      redis:
        condition: service_healthy
    restart: unless-stopped

  feature_engineering_service:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.features.feature_engineering_service
    env_file: .env
    depends_on:
      redpanda:
        condition: service_started
    restart: unless-stopped

  llm_agent_service:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.hybrid_engine.agents.news_analyst
    env_file: .env
    environment:
      LLM_ENDPOINT: ${LLM_ENDPOINT}
    depends_on:
      redpanda:
        condition: service_started
      redis:
        condition: service_healthy
    restart: unless-stopped

  signal_fusion_engine:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: python -m app.hybrid_engine.fusion.signal_fusion_engine
    env_file: .env
    depends_on:
      redpanda:
        condition: service_started
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped
```

**New env vars to add to `.env.example`:**
```bash
# LLM Agent
LLM_ENDPOINT=http://localhost:8000/v1/chat/completions
LLM_MODEL=nvidia/nemotron-4-340b-instruct
LLM_TIMEOUT_SECONDS=10

# Hybrid Engine
MIN_SIGNAL_CONFIDENCE=0.6
MAX_SIGNAL_AGE_SECONDS=300
SIGNAL_CONFLICT_THRESHOLD=0.5

# Scrapling
SCRAPLING_POLL_INTERVAL_SECONDS=120
SCRAPLING_RATE_LIMIT_PER_DOMAIN=0.5
```

---

## 📡 8️⃣ Observability

Every service logs using the existing `app.core.logging` structured logger.

**Required log fields per stage:**

| Stage | Fields |
|---|---|
| Tick ingested | `symbol`, `price`, `source`, `latency_ms` |
| Article scraped | `url`, `source`, `entities_found`, `latency_ms` |
| LLM analyzed | `asset`, `sentiment`, `confidence`, `llm_latency_ms` |
| Signal fused | `asset`, `action`, `final_score`, `contributors` |
| Signal published | `asset`, `topic`, `offset`, `e2e_latency_ms` |

**Prometheus metrics to expose (add to `/metrics`):**
```
hybrid_ticks_ingested_total{source, exchange}
hybrid_articles_scraped_total{source}
hybrid_llm_latency_seconds{model}
hybrid_signal_confidence{asset}
hybrid_e2e_latency_seconds{asset}
hybrid_signals_published_total{action}
```

---

## 🛡️ 9️⃣ Failure Handling Matrix

| Failure | Detection | Action |
|---|---|---|
| Scrapling site unreachable | HTTP 4xx/5xx or timeout | Retry 3× exp backoff, then skip + alert |
| LLM timeout | >10s response | Skip article, use keyword fallback |
| LLM invalid JSON | JSON parse error | Retry once with stricter prompt, then skip |
| Bad tick (price spike) | >10% price change | Discard, log `WARN` |
| Stale signal | age > 300s | Drop from fusion, log `WARN` |
| Conflicting signals | \|market - news\| > 0.5 | Emit `HOLD`, log conflict |
| Redpanda unavailable | Producer exception | Buffer in Redis list, replay on reconnect |
| Redis unavailable | Connection error | Disable dedup (allow duplicates), log `ERROR` |
| InfluxDB unavailable | Write exception | Log + continue (non-blocking) |

---

## ✅ 10️⃣ Implementation Order

Implement in this exact sequence to avoid blocked dependencies:

```
Step 1 — Infrastructure
  └── Add Redpanda topics (rpk topic create)
  └── Add PostgreSQL tables (Alembic migration)

Step 2 — Data Producers
  └── market_data_service.py
  └── macro_data_service.py
  └── scrapling_intelligence_service (extend existing)

Step 3 — Processing
  └── normalization_service.py
  └── feature_engineering_service.py (extend existing features/)

Step 4 — LLM Layer
  └── news_analyst.py
  └── macro_analyst.py
  └── commodity_analyst.py

Step 5 — Fusion
  └── signal_fusion_engine.py
  └── commodity_intelligence_engine.py

Step 6 — Integration
  └── hybrid_signals.py (API route)
  └── Wire unified_signal consumer into engine/service.py

Step 7 — Observability
  └── Add Prometheus metrics
  └── Add Grafana dashboard
```

---

## 🎯 Success Criteria

| Metric | Target |
|---|---|
| End-to-end latency (tick → signal) | < 1 second |
| News → LLM signal latency | < 15 seconds |
| Signal confidence (average) | > 0.70 |
| Scrapling uptime | > 99% |
| False signal rate | < 10% |
| Multi-source agreement rate | > 60% of BUY/SELL signals |

---

## 🧠 Design Principles

1. **Event-driven** — every component is a Redpanda consumer/producer. No polling between services.
2. **Fail-safe** — every failure path has an explicit handler. No silent failures.
3. **Stateless services** — all state in Redis/PG/InfluxDB. Services can restart freely.
4. **LLM is advisory only** — LLM output feeds fusion weights, never directly triggers orders.
5. **Confidence gating** — signals below `MIN_SIGNAL_CONFIDENCE` are silently dropped before reaching the trading engine.
6. **Minimal latency** — normalization and feature engineering are in-process (no extra network hop). Only LLM and fusion are separate consumers.
