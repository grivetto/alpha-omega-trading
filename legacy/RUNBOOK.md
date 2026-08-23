# Denaro Runbook — Deployment, Monitoring, Recovery

## Architecture

```
Nuvola (DOGE/EUR) ─── Grid Trading → EUR 100 baseline
MARCODG1 (DOGE/EUR) ─── Grid Trading → EUR 100 baseline
```

**Files (in deploy order):**

| File | Purpose |
|------|---------|
| `main.py` | Orchestrator: health server, signal handling, main loop |
| `denaro_core.py` | Risk engine: Kelly sizing, CB, ATR, compounding |
| `kraken_engine.py` | Kraken adapter: WebSocket price, retry, rate-limiting |
| `notifier.py` | Telegram notifications with rate limit + dedup |
| `enhanced/health_server.py` | HTTP /health, /metrics, /status (port 8909) |
| `mock_runner.py` | Local simulation for backtesting |
| `test_denaro_core.py` | Unit tests for core risk logic |
| `test_kraken_engine.py` | Unit tests for retry/error classification |


## Deploy

### Prerequisites

- SSH keys for `sergio@nuvola` and `marco@MARCODG1`
- `sergio` has passwordless sudo on nuvola
- `marco` has passwordless sudo on MARCODG1
- Both machines have `~/.env` configured
- Both machines have a Python venv at `~/denaro/venv/`

### Standard deploy

```bash
# Dry-run (shows what would happen)
./deploy.sh

# Live deploy to both machines
./deploy.sh --live

# Single machine
./deploy.sh --live --nuvola
./deploy.sh --live --marcodg1
```

### Manual deploy steps

```bash
# Build
cd /home/sergio/denaro  # local checkout
rsync -avz . sergio@nuvola:denaro/new_denaro/ --exclude __pycache__ --exclude .git --exclude _archive --exclude .env --exclude venv
rsync -avz . marco@MARCODG1:denaro/new_denaro/ --exclude __pycache__ --exclude .git --exclude _archive --exclude .env --exclude venv

# Install deps
ssh sergio@nuvola "cd denaro/new_denaro && pip install -r requirements.txt"
ssh marco@MARCODG1 "cd denaro/new_denaro && pip install -r requirements.txt"

# Replace + restart
ssh sergio@nuvola "
  cp -a denaro/new_denaro/* denaro/ && rm -rf denaro/new_denaro && \
  sudo systemctl daemon-reload && sudo systemctl restart denaro-kraken.service"
ssh marco@MARCODG1 "
  cp -a denaro/new_denaro/* denaro/ && rm -rf denaro/new_denaro && \
  sudo systemctl daemon-reload && sudo systemctl restart denaro-kraken-marcodg1.service"
```


## Monitoring

### Logs

```bash
# Live tail
sudo journalctl -u denaro-kraken.service -f                    # nuvola
sudo journalctl -u denaro-kraken-marcodg1.service -f           # MARCODG1

# Last status
sudo journalctl -u denaro-kraken.service -n 30 --no-pager | grep -E "(Eq:EUR|CB|ERROR|FILL)"
```

### Health HTTP API

Each machine exposes a health endpoint on `127.0.0.1:8909`:

```bash
# JSON health
curl -s http://127.0.0.1:8909/health | python -m json.tool

# Prometheus metrics
curl -s http://127.0.0.1:8909/met rics

# HTML status page
curl -s http://127.0.0.1:8909/status

# Ready check (200 = good, 503 = not ready)
curl -w "\nHTTP %{http_code}\n" http://127.0.0.1:8909/ready
```

### Key metrics (Prometheus endpoint at /metrics)

| Metric | Type | Description |
|--------|------|-------------|
| `denaro_equity` | gauge | Current portfolio value in EUR |
| `denaro_pnl_pct` | gauge | Total P&L % |
| `denaro_grid_levels` | gauge | Active grid levels |
| `denaro_error_count` | counter | Total error count |
| `denaro_ws_connected` | gauge | 1 if WS connected, 0 if not |
| `denaro_cb_state` | gauge | 0=CLOSED, 1=HALF_OPEN, 2=OPEN |

### Telegram alerts

If `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`:

- 🚀 Startup with key params
- 🧊 CB OPEN / 🔥 CB CLOSED
- 🔌 Shutdown
- 💹 Trade fills (buy/sell with P&L)
- ⚠️ Persistent errors


## Recovery Procedures

### Circuit Breaker triggered

1. Check logs: `sudo journalctl -u denaro-kraken.service -n 50 | grep CB`
2. Identify root cause (daily loss, drawdown, consecutive losses)
3. The CB auto-resets on next cycle when conditions normalise
4. To emergency reset the CB:
   ```bash
   # Delete state file (loses trade history)
   rm -f ~/denaro/denaro_core_state.json
   sudo systemctl restart denaro-kraken.service
   ```

### Grid stuck (all levels filled, no new orders)

1. Check `kraken_state.json` — active levels
2. If all levels are filled with no sell orders active:
   ```bash
   # Cancel all orders and restart
   python tools/cancel_all_kraken.py
   sudo systemctl restart denaro-kraken.service
   ```

### Bot not responding / health check fails

1. Check service status: `systemctl status denaro-kraken.service`
2. Check recent logs: `journalctl -u denaro-kraken.service -n 30`
3. If OOM killed: `dmesg | grep -i oom`
4. Restart: `sudo systemctl restart denaro-kraken.service`
5. Check journal for startup errors: `journalctl -u denaro-kraken.service -n 50 --no-pager`

### WebSocket disconnected

The bot falls back to REST polling automatically.
To force WS restart: restart the service.
To disable WS permanently: add `KRAKEN_WS_DISABLE=1` to `.env`.


## System Administration

### Service management

```bash
sudo systemctl status denaro-kraken.service       # status + last logs
sudo systemctl restart denaro-kraken.service      # restart
sudo systemctl stop denaro-kraken.service         # stop
sudo systemctl start denaro-kraken.service        # start
sudo systemctl daemon-reload                      # after changing .service file
```

### Verify after deploy

```bash
# 1. Service is active
systemctl is-active denaro-kraken.service && echo "OK" || echo "FAIL"

# 2. Health endpoint responds
curl -sf http://127.0.0.1:8909/health && echo "OK" || echo "FAIL"

# 3. Recent cycle completed (last 5 seconds)
LAST=$(journalctl -u denaro-kraken.service -n 1 --no-pager -o cat | grep -oP 'Eq:EUR[ \d.]+')
echo "Last cycle: $LAST"

# 4. No errors in last 50 lines
journalctl -u denaro-kraken.service -n 50 --no-pager | grep -c "ERROR"
```


## Local Development

### Quick test (mock mode)
```bash
python -u main.py
# Set MOCK_MODE=1 in .env to run without API keys
```

### Run tests
```bash
pip install pytest
python -m pytest test_denaro_core.py test_kraken_engine.py -v --tb=short
```

### Docker (local)
```bash
docker compose up denaro-mock
# Health: http://localhost:8909/health
```

### SSH cheat sheet
```bash
ssh nuvola                                 # sergio@nuvola (key-based)
ssh MARCODG1                               # marco@MARCODG1 (key-based)
ssh -t nuvola 'sudo journalctl -f -u denaro-kraken.service'
ssh -t MARCODG1 'sudo journalctl -f -u denaro-kraken-marcodg1.service'
```
