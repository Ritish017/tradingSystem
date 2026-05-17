# Production Deployment Guide

## Pre-Deployment Checklist

### 1. Secrets Management

**Development (Current):**
- Secrets in `.env` file (never commit)
- Copy `.env.example` to `.env` and fill in values

**Production (Required):**
```bash
# Option A: HashiCorp Vault
export VAULT_ADDR="https://vault.example.com"
export VAULT_TOKEN="your-token"

# Option B: AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id trading-platform/prod

# Option C: Kubernetes Secrets
kubectl create secret generic trading-secrets \
  --from-literal=postgres-password=xxx \
  --from-literal=redis-password=xxx \
  --from-literal=kite-api-key=xxx
```

### 2. Database Backups

**Postgres:**
```bash
# Automated hourly backups to S3
0 * * * * pg_dump -U postgres trading_db | gzip | aws s3 cp - s3://backups/postgres/$(date +\%Y\%m\%d-\%H\%M).sql.gz

# Point-in-time recovery setup
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://backups/postgres/wal/%f'
```

**InfluxDB:**
```bash
# Retention policy: tick data 30 days, OHLCV forever
influx -execute 'CREATE RETENTION POLICY "30d" ON "market_data" DURATION 30d REPLICATION 1 DEFAULT'
influx -execute 'CREATE RETENTION POLICY "infinite" ON "market_data" DURATION INF REPLICATION 1'

# Daily backup
influxd backup -portable -database market_data /backups/influx/$(date +\%Y\%m\%d)
```

### 3. TLS/mTLS Configuration

**Generate certificates:**
```bash
# Self-signed for internal services
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Production: Use Let's Encrypt or corporate CA
certbot certonly --standalone -d trading.example.com
```

**Nginx reverse proxy:**
```nginx
server {
    listen 443 ssl http2;
    server_name trading.example.com;
    
    ssl_certificate /etc/letsencrypt/live/trading.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trading.example.com/privkey.pem;
    
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location / {
        proxy_pass http://frontend:3000;
    }
}
```

### 4. Kubernetes Deployment

**Namespace:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: trading-platform
```

**Backend Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-backend
  namespace: trading-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: trading-backend
  template:
    metadata:
      labels:
        app: trading-backend
    spec:
      containers:
      - name: backend
        image: trading-platform/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: postgres-password
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

**Service:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: trading-backend
  namespace: trading-platform
spec:
  selector:
    app: trading-backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 5. Monitoring & Alerting

**Prometheus scrape config:**
```yaml
scrape_configs:
  - job_name: 'trading-backend'
    static_configs:
      - targets: ['trading-backend:8000']
    metrics_path: '/metrics'
```

**Grafana alerts:**
```yaml
# Kill switch fired
- alert: KillSwitchActivated
  expr: trading_halted == 1
  for: 1m
  annotations:
    summary: "Trading halted"
    
# Daily loss limit approaching
- alert: DailyLossLimitWarning
  expr: (daily_realized_pnl / capital) < -0.015
  for: 5m
  annotations:
    summary: "Daily loss at 1.5% (limit 2%)"
    
# Strategy circuit broken
- alert: StrategyCircuitBroken
  expr: strategy_consecutive_losses >= 3
  annotations:
    summary: "Strategy {{ $labels.strategy_name }} circuit broken"
```

**Telegram bot for alerts:**
```python
import requests

def send_telegram_alert(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message})
```

### 6. Compliance & Audit Log

**Trade log export (monthly):**
```python
# backend/app/api/routes/compliance.py
@router.get("/export/trades")
async def export_trades(start_date: str, end_date: str):
    """Export all trades for tax/audit purposes."""
    query = """
        SELECT 
            created_at,
            strategy_name,
            symbol,
            side,
            quantity,
            entry_price,
            exit_price,
            realised_pnl,
            fees,
            stt,
            gst
        FROM trades
        WHERE created_at BETWEEN %s AND %s
        ORDER BY created_at
    """
    # Return CSV with all SEBI-required fields
```

### 7. Go-Live Checklist

**Before enabling live trading:**

- [ ] Minimum 3 months of paper trading completed
- [ ] All strategies have positive Sharpe > 1.0 in paper mode
- [ ] Daily PnL variance understood and acceptable
- [ ] Max drawdown in paper mode < 10%
- [ ] Broker API credentials tested on sandbox
- [ ] Kill switch tested and working
- [ ] All risk limits tested (trigger daily loss limit in paper, verify halt)
- [ ] Backup and restore procedures tested
- [ ] Disaster recovery runbook reviewed
- [ ] Monitoring and alerting tested
- [ ] Team trained on emergency procedures
- [ ] Start with MINIMUM position size (1 share / 1 lot)
- [ ] Capital allocation: Start with ₹10,000 max
- [ ] Review after 1 week, 1 month, 3 months before scaling

---

## Disaster Recovery Runbook

### Scenario 1: Engine Crashes Mid-Trade

**Symptoms:** Backend pod crashes, open orders in unknown state

**Actions:**
1. **Immediate:** Activate kill switch via UI or API
   ```bash
   curl -X POST https://trading.example.com/api/risk/kill-switch \
     -H "Content-Type: application/json" \
     -d '{"reason": "engine_crash"}'
   ```

2. **Reconcile positions:**
   ```bash
   # Fetch positions from broker
   python scripts/reconcile_positions.py --broker zerodha
   
   # Compare with engine state
   # Flag mismatches for manual review
   ```

3. **Check order status:**
   ```bash
   # Query broker for all orders placed today
   # Update engine state with actual fills
   ```

4. **Restart engine:**
   ```bash
   kubectl rollout restart deployment/trading-backend -n trading-platform
   ```

5. **Verify health:**
   ```bash
   curl https://trading.example.com/healthz
   ```

6. **Resume trading only after:**
   - All positions reconciled
   - No state mismatches
   - Root cause identified

### Scenario 2: Broker API Disconnection

**Symptoms:** Orders failing, WebSocket disconnected

**Actions:**
1. **Automatic:** Engine should detect and halt new orders
2. **Manual:** Check broker status page
3. **Fallback:** Switch to backup broker (if configured)
   ```python
   # In engine config
   BROKER_FAILOVER = ["zerodha", "shoonya", "upstox"]
   ```
4. **Do NOT:** Place manual orders outside the system (breaks state)

### Scenario 3: Data Gap (Missing Ticks)

**Symptoms:** InfluxDB shows gap in tick data

**Actions:**
1. **Immediate:** Strategies using affected symbols should halt
2. **Backfill:**
   ```bash
   python scripts/backfill_data.py \
     --symbols RELIANCE,TCS \
     --start 2024-01-15T09:15:00 \
     --end 2024-01-15T15:30:00
   ```
3. **Verify:** Check feature cache invalidation
4. **Resume:** Only after data integrity confirmed

### Scenario 4: Accidental Over-Leverage

**Symptoms:** Gross exposure > 100%, margin call from broker

**Actions:**
1. **Immediate:** Kill switch
2. **Close positions:** Start with highest loss positions
3. **Root cause:** Check risk gate logs
   ```bash
   kubectl logs -n trading-platform deployment/trading-backend | grep "risk_gate"
   ```
4. **Fix:** Update risk limits, add missing checks
5. **Post-mortem:** Document and add test case

### Scenario 5: Strategy Gone Rogue

**Symptoms:** One strategy generating excessive orders, rapid losses

**Actions:**
1. **Immediate:** Disable strategy via API
   ```bash
   curl -X POST https://trading.example.com/api/strategies/supertrend_rsi/disable
   ```
2. **Close positions:** Liquidate all positions from that strategy
3. **Review:** Check strategy logs, signal history
4. **Circuit breaker:** Should have triggered at 3 losses (verify)
5. **Fix:** Update strategy logic, add safeguards
6. **Re-enable:** Only after thorough testing in paper mode

---

## Performance Optimization

### Database Indexing
```sql
-- Trades table
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX idx_trades_strategy ON trades(strategy_name);
CREATE INDEX idx_trades_symbol ON trades(symbol);

-- Orders table
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
```

### Redis Optimization
```bash
# Increase max memory
maxmemory 2gb
maxmemory-policy allkeys-lru

# Enable persistence
save 900 1
save 300 10
save 60 10000
```

### InfluxDB Optimization
```bash
# Shard duration for high-frequency data
CREATE RETENTION POLICY "1d_shards" ON "market_data" DURATION 30d REPLICATION 1 SHARD DURATION 1d
```

---

## Security Hardening

1. **Network policies:** Restrict pod-to-pod communication
2. **RBAC:** Limit API access by role
3. **Audit logging:** Log all kill switch activations, strategy changes
4. **Rate limiting:** Prevent API abuse
5. **Input validation:** Sanitize all user inputs
6. **Secrets rotation:** Rotate API keys every 90 days

---

## Scaling Considerations

**Horizontal scaling:**
- Backend: 2-5 replicas behind load balancer
- Frontend: 2-3 replicas
- Databases: Read replicas for queries

**Vertical scaling:**
- InfluxDB: 8GB+ RAM for tick data
- Postgres: 4GB+ RAM
- Redis: 2GB+ RAM

**Cost optimization:**
- Use spot instances for non-critical workloads
- Archive old data to S3 Glacier
- Optimize InfluxDB retention policies
