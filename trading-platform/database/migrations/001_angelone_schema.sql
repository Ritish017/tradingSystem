-- Angel One integration schema
-- Run against PostgreSQL with TimescaleDB extension

-- Enable TimescaleDB (requires the extension installed)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ── Instrument cache ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrument_cache (
    token          TEXT        NOT NULL,
    symbol         TEXT        NOT NULL,
    exchange       TEXT        NOT NULL,
    name           TEXT,
    expiry         DATE,
    strike         NUMERIC(12, 2),
    option_type    TEXT,           -- CE / PE / NULL
    lot_size       INTEGER     DEFAULT 1,
    tick_size      NUMERIC(8, 4) DEFAULT 0.05,
    instrument_type TEXT,          -- EQ, FUTSTK, OPTSTK, OPTIDX, etc.
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (token, exchange)
);

CREATE INDEX IF NOT EXISTS idx_instrument_symbol ON instrument_cache (symbol, exchange);
CREATE INDEX IF NOT EXISTS idx_instrument_expiry  ON instrument_cache (expiry) WHERE expiry IS NOT NULL;

-- ── OHLC candles (hypertable) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candles (
    symbol      TEXT        NOT NULL,
    exchange    TEXT        NOT NULL DEFAULT 'NSE',
    timeframe   TEXT        NOT NULL,   -- 1m, 5m, 15m, 1h, 1d
    ts          TIMESTAMPTZ NOT NULL,
    open        NUMERIC(14, 4) NOT NULL,
    high        NUMERIC(14, 4) NOT NULL,
    low         NUMERIC(14, 4) NOT NULL,
    close       NUMERIC(14, 4) NOT NULL,
    volume      BIGINT      NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, timeframe, ts)
);

-- Convert to hypertable partitioned by time (7-day chunks)
SELECT create_hypertable('candles', 'ts',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf ON candles (symbol, timeframe, ts DESC);

-- Retention: keep 2 years of candle data
SELECT add_retention_policy('candles',
    INTERVAL '2 years',
    if_not_exists => TRUE);

-- Continuous aggregate: daily OHLCV (materialised view)
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', ts) AS day,
    symbol,
    exchange,
    first(open, ts)   AS open,
    max(high)         AS high,
    min(low)          AS low,
    last(close, ts)   AS close,
    sum(volume)       AS volume
FROM candles
WHERE timeframe = '1m'
GROUP BY day, symbol, exchange
WITH NO DATA;

-- ── Option chain snapshots ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS option_snapshots (
    id          BIGSERIAL,
    symbol      TEXT        NOT NULL,
    expiry      DATE        NOT NULL,
    strike      NUMERIC(12, 2) NOT NULL,
    option_type TEXT        NOT NULL,   -- CE / PE
    ltp         NUMERIC(12, 4),
    oi          BIGINT,
    oi_change   BIGINT,
    iv          NUMERIC(8, 4),
    delta       NUMERIC(8, 6),
    gamma       NUMERIC(10, 8),
    theta       NUMERIC(8, 4),
    vega        NUMERIC(8, 4),
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

SELECT create_hypertable('option_snapshots', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_opt_snap_symbol ON option_snapshots (symbol, expiry, strike, option_type, ts DESC);

-- ── Orders (from Angel One) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT        PRIMARY KEY,
    symbol          TEXT        NOT NULL,
    exchange        TEXT        NOT NULL,
    side            TEXT        NOT NULL,   -- BUY / SELL
    order_type      TEXT        NOT NULL,   -- MARKET / LIMIT / etc.
    product_type    TEXT,
    quantity        INTEGER     NOT NULL,
    price           NUMERIC(14, 4),
    trigger_price   NUMERIC(14, 4),
    status          TEXT,
    filled_qty      INTEGER     DEFAULT 0,
    avg_fill_price  NUMERIC(14, 4),
    strategy_name   TEXT,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

-- ── Trades ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trades (
    trade_id        TEXT        PRIMARY KEY,
    order_id        TEXT        REFERENCES orders (order_id) ON DELETE SET NULL,
    symbol          TEXT        NOT NULL,
    exchange        TEXT        NOT NULL,
    side            TEXT        NOT NULL,
    quantity        INTEGER     NOT NULL,
    trade_price     NUMERIC(14, 4) NOT NULL,
    product_type    TEXT,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Portfolio snapshots (daily) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              BIGSERIAL   PRIMARY KEY,
    snapshot_date   DATE        NOT NULL DEFAULT CURRENT_DATE,
    symbol          TEXT        NOT NULL,
    exchange        TEXT        NOT NULL,
    quantity        INTEGER     NOT NULL,
    avg_price       NUMERIC(14, 4),
    close_price     NUMERIC(14, 4),
    market_value    NUMERIC(16, 4),
    unrealized_pnl  NUMERIC(16, 4),
    realized_pnl    NUMERIC(16, 4),
    UNIQUE (snapshot_date, symbol, exchange)
);

-- ── Tick data (raw, short retention) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticks (
    symbol  TEXT        NOT NULL,
    source  TEXT        NOT NULL,   -- angelone / binance
    price   NUMERIC(14, 4) NOT NULL,
    volume  NUMERIC(18, 4),
    ts      TIMESTAMPTZ NOT NULL
);

SELECT create_hypertable('ticks', 'ts',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- Keep only 7 days of raw ticks
SELECT add_retention_policy('ticks',
    INTERVAL '7 days',
    if_not_exists => TRUE);
