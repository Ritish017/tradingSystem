# Advanced India + Crypto Algorithmic Trading Platform

Production-grade, self-learning algorithmic trading platform combining rule-based, machine-learning, and reinforcement-learning strategies for Indian markets (NSE/BSE equities, NFO F&O, MCX) and crypto (Binance, OKX).

## ⚠️ Reality Check

**READ THIS BEFORE RUNNING:**

- Most retail algo traders **lose money**. This platform provides infrastructure, not guaranteed profits.
- **Minimum 3 months of paper trading** required before risking real capital.
- Start live trading with **minimum position sizes** (1 share / 1 lot).
- SEBI registration required for managing third-party funds.
- F&O profits taxed as business income in India.

## Features

### Core Capabilities
- ✅ **Multi-asset support:** NSE/BSE equities, NFO F&O, MCX commodities, crypto
- ✅ **10 strategies:** 5 rule-based, 3 ML alpha, 2 RL agents
- ✅ **Paper trading:** Realistic slippage and cost simulation
- ✅ **Live execution:** Zerodha, Shoonya, Upstox, Angel One (via OpenAlgo)
- ✅ **Self-learning:** Nightly RL retraining on real trade outcomes
- ✅ **Risk management:** Hard limits, circuit breakers, kill switch
- ✅ **Backtesting:** Vectorbt with realistic Indian tax/fee models
- ✅ **Observability:** Grafana dashboards, Prometheus metrics, MLflow tracking

### Strategy Library

**Rule-Based:**
1. Opening Range Breakout (Indian intraday classic)
2. Supertrend + RSI crossover
3. Crypto momentum (20-period)
4. Mean reversion (Z-score)
5. BankNifty short straddle (low vol)

**ML Alpha:**
1. LightGBM next-day return prediction
2. LSTM sequence prediction
3. Transformer attention-based

**RL Agents:**
1. PPO (Proximal Policy Optimization)
2. TD3 (Twin Delayed DDPG)

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI + Python 3.11 | Async API, typed |
| Frontend | Next.js 14 + TypeScript | Modern UI |
| Trading Engine | nautilus_trader | Paper + live execution |
| Time-series DB | InfluxDB 2.x | Tick/OHLCV storage |
| Cache | Redis 7 | Position state, pub/sub |
| Database | PostgreSQL 16 | Trade audit log |
| Event Stream | Redpanda | Kafka-compatible |
| ML Tracking | MLflow | Model versioning |
| Monitoring | Grafana + Prometheus | Dashboards, alerts |
| Orchestration | Docker Compose / K8s | Deployment |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 1. Clone and Setup
```bash
git clone <repo-url>
cd trading-platform

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# CRITICAL: Never commit .env
```

### 2. Start Infrastructure
```bash
docker-compose up -d

# Verify all services running
docker-compose ps
```

### 3. Install Dependencies
```bash
# Backend
cd backend
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

### 4. Run Database Migrations
```bash
cd backend
alembic upgrade head
```

### 5. Seed Historical Data (Optional)
```bash
python scripts/seed_historical_data.py \
  --symbols RELIANCE,TCS,INFY \
  --start 2020-01-01 \
  --end 2024-01-01
```

### 6. Start Application
```bash
# Backend (terminal 1)
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm run dev
```

### 7. Access UI
- Dashboard: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Grafana: http://localhost:3001 (admin/admin)
- MLflow: http://localhost:5000

## Usage

### Run Backtest
```bash
python scripts/run_backtest.py \
  --strategy supertrend_rsi \
  --symbols RELIANCE,TCS \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --capital 100000 \
  --market nse_equity

# Output: QuantStats tearsheet + MLflow run
```

### Start Paper Trading
```bash
# Register strategies
curl -X POST http://localhost:8000/api/strategies/register

# Enable paper trading mode
curl -X POST http://localhost:8000/api/strategies/supertrend_rsi/enable \
  -H "Content-Type: application/json" \
  -d '{"mode": "paper"}'

# Monitor via dashboard
open http://localhost:3000/strategies
```

### Activate Kill Switch
```bash
# Via API
curl -X POST http://localhost:8000/api/risk/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"reason": "manual_halt"}'

# Or via UI: Dashboard → Kill Switch button
```

## Configuration

### Risk Limits (`configs/features/default.yml`)
```yaml
risk:
  max_daily_loss_pct: 0.02          # 2% daily loss → halt
  max_position_concentration_pct: 0.20  # 20% per instrument
  max_gross_exposure_pct: 1.00      # No leverage in paper
  max_fo_margin_utilisation_pct: 0.60   # 60% F&O margin
  circuit_breaker_losses: 3         # 3 losses → review
```

### Feature Sets
```yaml
indicators:
  rule_based:
    - rsi_14
    - ema_20
    - ema_50
    - supertrend_10_3
  ml_alpha:
    - returns_1d
    - returns_5d
    - volatility_20d
    - volume_zscore_20d
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                   │
│  Dashboard │ Strategies │ Positions │ Risk │ Backtest       │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Ingestion   │  │   Features   │  │  Strategies  │     │
│  │  (Kite/CCXT) │  │  (pandas-ta) │  │  (10 total)  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼───────┐    │
│  │           Master Engine (nautilus_trader)          │    │
│  │  Signal Aggregator → Position Sizer → Risk Gate   │    │
│  └──────┬─────────────────────────────────────────────┘    │
│         │                                                    │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Paper Exec   │  │ India (OA)   │  │ Crypto (ccxt)│    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└────────────────────────────────────────────────────────────┘
         │                  │                  │
┌────────▼──────┐  ┌────────▼──────┐  ┌────────▼──────┐
│  InfluxDB     │  │  PostgreSQL   │  │    Redis      │
│  (Ticks)      │  │  (Trades)     │  │  (State)      │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Cost Models

### Indian Equity (Zerodha)
- **Intraday:** ₹20 or 0.03% (whichever lower)
- **Delivery:** ₹0 brokerage
- **STT:** 0.025% (intraday), 0.1% (delivery)
- **Exchange charges:** 0.00325%
- **GST:** 18% on brokerage + exchange
- **Stamp duty:** 0.003% (intraday), 0.015% (delivery)

### NFO F&O
- **Brokerage:** ₹20 or 0.03%
- **STT:** 0.0125% (futures), 0.05% (options)
- **Exchange:** 0.0019%

### Crypto
- **Binance:** 0.1% maker/taker
- **OKX:** 0.08% maker, 0.1% taker

## Testing

```bash
# Unit tests
cd backend
pytest app/tests/unit -v

# Integration tests
pytest app/tests/integration -v

# Strategy backtests
pytest app/tests/strategies -v

# Linting
ruff check .
mypy app
```

## Monitoring

### Grafana Dashboards
1. **Ingestion:** Ticks/sec by source, publish failures
2. **Execution:** Fill quality, slippage distribution
3. **PnL:** Live equity curve, drawdown, Sharpe
4. **Risk:** Exposure usage, limit breaches

### Prometheus Alerts
- Kill switch activated
- Daily loss limit approaching (1.5%)
- Strategy circuit broken
- Broker disconnection
- Data gap detected

## Production Deployment

See [PRODUCTION.md](./PRODUCTION.md) for:
- Secrets management (Vault / AWS Secrets Manager)
- Kubernetes manifests
- Backup procedures
- Disaster recovery runbook
- Go-live checklist

## Compliance

### Trade Log Export
```bash
# Monthly export for CA/tax filing
curl "http://localhost:8000/api/compliance/export/trades?start=2024-01-01&end=2024-01-31" \
  > trades_jan2024.csv
```

### Required Fields (SEBI)
- Trade date/time
- Symbol, quantity, price
- Brokerage, STT, GST, stamp duty
- Realized PnL
- Strategy attribution

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Common issues:
# 1. Port 8000 already in use
# 2. Database connection failed (check .env)
# 3. Missing dependencies (pip install -e .)
```

### No tick data
```bash
# Check ingestion service
curl http://localhost:8000/metrics | grep ingestion

# Verify Kite WebSocket enabled
# KITE_WS_ENABLED=true in .env
```

### Backtest fails
```bash
# Ensure historical data seeded
python scripts/seed_historical_data.py --symbols RELIANCE --start 2023-01-01 --end 2023-12-31

# Check InfluxDB
influx -execute 'SELECT COUNT(*) FROM market_data.autogen.ohlcv'
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

**Code standards:**
- Type hints everywhere (mypy strict)
- Tests for new features
- Docstrings for public APIs
- Ruff formatting

## License

MIT License - see LICENSE file

## Disclaimer

**This software is for educational purposes only. Use at your own risk.**

- No warranty of profitability
- Past performance ≠ future results
- Algorithmic trading carries significant risk of loss
- Consult a financial advisor before trading
- Authors not liable for trading losses

## Support

- Documentation: [docs/](./docs/)
- Issues: GitHub Issues
- Discussions: GitHub Discussions

## Roadmap

- [ ] Multi-broker failover
- [ ] Options Greeks calculation
- [ ] Portfolio optimization (Markowitz, Black-Litterman)
- [ ] Sentiment analysis (news, social media)
- [ ] Advanced order types (iceberg, TWAP, VWAP)
- [ ] Mobile app (React Native)
- [ ] Cloud deployment templates (AWS, GCP, Azure)

---

**Built with ❤️ for the Indian algo trading community**
