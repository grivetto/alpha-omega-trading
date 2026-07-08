# Denaro v5 — Bybit Spot Grid Trading

> **DOGE/USDT grid trading su Bybit con Kelly sizing, Circuit Breaker, ATR volatility scaling.**
> Progetto di **Sergio Grivetto** — co-autori Hermes AI, CodeWhale.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-BETA-yellow)]()
[![Exchange](https://img.shields.io/badge/Exchange-Bybit%20Spot%20USDT-purple)]()

---

## Cosa fa

**Sistema di trading autonomo su Bybit spot per DOGE/USDT.** Stessa architettura di Denaro v4 (Kraken), ma su Bybit con coppie USDT.

| Macchina | Pair | Exchange | Porta Health |
|----------|------|----------|--------------|
| **MARCODG1** | DOGE/USDT | Bybit Spot | 8911 |

---

## Architettura

```
├── main_v5.py         # Orchestratore v5 (Bybit)
├── bybit_engine.py    # Bybit adapter — CCXT + WS ticker/book
├── denaro_core.py     # Core engine condiviso — Kelly, CB, ATR, VaR (riusato da v4)
├── notifier.py        # Telegram (riusato da v4)
├── enhanced/
│   ├── health_server.py   # HTTP /health (riusato, porta 8911)
│   └── update_dashboard.py
└── denaro-bybit-marcodg1.service  # systemd per MARCODG1
```

### Ciclo principale (DOGE/USDT, ogni ~1s)

```
WS ticker → Balance refresh → Grid sync → Kelly sizing → ATR scaling → Order management → CB check → Health update
```

---

## Perché Bybit e non Kraken?

| | Kraken (v4) | Bybit (v5) |
|---|---|---|
| Pairs | EUR pairs | USDT pairs (più liquidi) |
| Fee | 0.16% maker / 0.26% taker | 0.1% maker / 0.1% taker |
| API | CCXT + WS Kraken | CCXT + WS Bybit v5 |
| Macchina | nuvola + MARCODG1 | MARCODG1 (affianca Kraken) |

---

## Configurazione (`.env`)

```ini
# Kraken keys (v4) — già presenti
KRAKEN_API=xxx
KRAKEN_SECRET=xxx

# Bybit keys (v5) — nuove
BYBIT_API_KEY=<api-key>
BYBIT_API_SECRET=<api-secret>

SYMBOL=DOGE/USDT
CURRENCY=USDT
CAPITAL=100.0
LEVELS=5
SPREAD=0.025
SHADOW_MODE=1          # 1 = simulato, 0 = live
```

---

## Deploy

### Prerequisiti su MARCODG1
```bash
# Aggiungi a .env
BYBIT_API_KEY=xxx
BYBIT_API_SECRET=xxx
SYMBOL=DOGE/USDT
CURRENCY=USDT
HEALTH_PORT=8911

# Installa requirements
cd /home/marco/denaro
source venv/bin/activate
pip install -r requirements.txt
```

### Copia service + start
```bash
sudo cp denaro-bybit-marcodg1.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable denaro-bybit-marcodg1.service
sudo systemctl start denaro-bybit-marcodg1.service
```

### Verifica
```bash
sudo systemctl status denaro-bybit-marcodg1.service
journalctl -u denaro-bybit-marcodg1.service -f
curl -sf http://127.0.0.1:8911/health
```

---

## Monitoring

```bash
# Log live
journalctl -u denaro-bybit-marcodg1.service -f

# Health check
curl http://127.0.0.1:8911/health
curl http://127.0.0.1:8911/metrics
```

Il bot condivide il Telegram notifier con v4 — stesse notifiche su canale Telegram.

---

## Risk Management (stesso di v4)

- **Kelly criterio** auto-aggiustante su win rate
- **Circuit Breaker**: 4 perdite → dimezza, 15% drawdown → STOP, 20% → GLOBAL STOP
- **Daily loss limit**: 5% del capitale
- **ATR volatility scaling**: spread adattivo
- **SHADOW_MODE**: default 10% simulato

---

## Versioni

| Versione | Exchange | Pair | Stato |
|----------|----------|------|-------|
| v4 | Kraken Spot | PEPE/EUR, WIF/EUR | LIVE ✅ |
| **v5** | **Bybit Spot** | **DOGE/USDT** | **BETA 🟡** |
