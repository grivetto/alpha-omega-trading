# Denaro — Kraken/Bybit Grid Trading v6

> **DOGE/EUR grid trading su Kraken (LIVE) + SOL/USDT Bybit (SHADOW)** con SHADOW_MODE, **Kelly sizing**, **Circuit Breaker**, **ATR volatility scaling**, **caching intelligente**, **lockout protection**.
> Progetto di **Sergio Grivetto** con **Hermes AI** — co-autori.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-NUVOLA%3A%20LIVE%20%E2%9C%85-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Kraken](https://img.shields.io/badge/Exchange-Kraken%20Spot%20EUR-yellow)]()

---

## Autori

| Chi | Ruolo |
|-----|-------|
| **Sergio Grivetto** | Fondatore, capitale, strategia, infrastruttura, decisioni |
| **CodeWhale AI** | Ingegneria v5, caching, lockout protection, automazione |

---

## Cosa fa

**Sistema di trading autonomo multi-exchange.** Grid trading adattivo con Kelly position sizing, ATR volatility scaling, circuit breaker integrato, caching intelligente e lockout protection. Sistema gestito da systemd per operatività 24/7.

| Macchina | Pair | Exchange | Capitale | Stato |
|----------|------|----------|----------|-------|
| **nuvola** | DOGE/EUR | Kraken | 100 EUR | **LIVE** ✅ |
| **MARCODG1** | SOL/USDT | Bybit | 100 USDT | SHADOW (key invalida) |

---

## v6 — Cosa è cambiato (fix critici produzione)

### 🔥 Circuit Breaker Auto-Recovery (ERA IL #1 BUG)
- **CB NON si blocca più per sempre** — dopo `CB_RECOVERY_MINUTES` (default 30 minuti)
  in stato OPEN, il bot forza automaticamente HALF_OPEN e riprova a fare trading.
- **Fix critico**: il recovery time-based ora viene valutato PRIMA dei check drawdown/daily-loss,
  così anche se il drawdown è ancora alto dopo il timeout, il bot sblocca il trading.
- **`since` preservato**: il timestamp originale del CB non viene sovrascritto a ogni restart,
  quindi il timer di recovery non si azzera.
- **Telegram notification rate-limit**: CB OPEN notificato massimo 1 volta ogni 5 minuti.
  Transizioni di stato (OPEN→HALF_OPEN→CLOSED) notificate singolarmente, non a ogni ciclo.

### 🛡️ Risk Limits (produzione)
- **MAX_DRAWDOWN_PCT=5%** (era 15% — troppo alto, ormai in drawdown era irreversibile)
- **MAX_DAILY_LOSS_PCT=2%** (era 5%)
- **CB_RECOVERY_MINUTES=30** (nuvola) / **60** (MARCODG1)

### 🔧 MARCODG1 — Bybit SHADOW Mode con fallback
- **BybitEngine init fallback**: se le chiavi API sono invalide, in SHADOW_MODE
  il bot usa MockKrakenEngine invece di crashare (exit(1)).
- **MockKrakenEngine flessibile**: supporta coppie USDT/qualsiasi base currency.
- **Service unificato**: `denaro.service` su MARCODG1 usa `run.py` → EXCHANGE=bybit.
  Vecchio `botv5.service` disabilitato (puntava a `bot_v5.py` rimosso).

### 🧹 Pulizia remota
- Rimossi 10+ file stale su nuvola e MARCODG1 (`_test_*.py`, `_gen_*.py`,
  `bot_v5.py`, `denaro_zabbix.py`, `deploy.py`, ecc.)
- **deploy.sh v6**: `sudo -n` per compatibilità MARCODG1, service name corretto,
  stop old `botv5.service` prima del deploy.

### 📊 Stato attuale
| Macchina | Pair | Exchange | Capitale | Equity | Stato |
|----------|------|----------|----------|--------|-------|
| **nuvola** | DOGE/EUR | Kraken | 100 EUR | **73.76 EUR** | **LIVE** ✅ (CB CLOSED) |
| **MARCODG1** | SOL/USDT | Bybit | 100 USDT | 100 USDT | SHADOW (key invalida → mock) |

---

## v5 — Cosa è cambiato (miglioramenti critici)

### 🚨 Lockout Protection (CRITICAL — nuvola era bloccata)
- **Balance caching**: `BALANCE_CACHE_TTL=15s` — riduce chiamate REST del 70%+
- **Orders caching**: `ORDERS_CACHE_TTL=10s`
- **Error classification**: separa errori PERMANENTI (Invalid key) da temporanei
- **Lockout backoff**: esponenziale 30s → 60s → 120s → max 600s
- **Deep sleep mode**: dopo 5 fallimenti consecutivi, controlla solo ogni 60s
- **PermanentError**: Invalid key → shutdown immediato (no hammer)

### 🎯 Performance
- **WS-first price**: zero chiamate REST quando WS è connesso
- **Cache-aware balance**: refresh ogni 15s, non ogni ciclo
- **Fetch open orders**: refresh ogni 10s, non ogni ciclo
- **API stats tracking**: calls, cache-hits, lockout state via health endpoint

### 🛡️ Resilience
- **Graceful degradation**: errori API non bloccano il ciclo
- **Deep sleep**: entra in sleep profondo dopo N fallimenti
- **State recovery**: ripristino grid dopo lockout
- **Risk limits da .env**: MAX_DRAWDOWN_PCT, MAX_DAILY_LOSS_PCT parametrizzati

---

## Strategie

### Grid Trading (100% del capitale)
- **SHADOW_MODE default** — trading simulato per test, live con SHADOW_MODE=0
- **5 livelli** BUY equidistanti sotto, SELL sopra il prezzo corrente
- **Spread adattivo** = ATR × 0.8 (scalatura volatilità)
- **Kelly position sizing** — auto-aggiustante basato su win rate
- **Compounding** — reinvestimento automatico dei profitti

### Risk Management
- **Kelly criterio** auto-aggiustante — win rate su ultime 50 operazioni
- **Circuit Breaker**:
  - 4 perdite consecutive → dimezza sizing
  - Drawdown > 5% → STOP pair
  - Daily loss > 2% → STOP giornaliero
- **ATR volatility scaling** — spread e sizing adattati

---

## Architettura v5

```
├── main.py              # KrakenBot v5 — orchestrator, caching, backoff
├── denaro_core.py       # Core engine — Kelly, CB, ATR, regime detection
├── kraken_engine.py     # Kraken v5 — WS + REST, caching, lockout protection
├── bybit_engine.py      # Bybit v5 — stesso pattern di KrakenEngine
├── notifier.py          # Telegram notifier + lockout/cb/invalid key alerts
├── mock_runner.py       # Mock engine per test offline
├── deploy.sh            # Deploy script v5 — jump-host per MARCODG1
├── run.py               # Exchange router (EXCHANGE=kraken|bybit|mexc)
├── enhanced/
│   └── health_server.py # HTTP health endpoint + Prometheus metrics
└── _archive/            # Versioni precedenti
```

### Ciclo principale (cache-aware)

```
WS ticker → Balance cache (TTL) → Risk check → Grid sync → Order mgmt → Health
                                                            ↓
                                              Lockout? → Backoff → Deep sleep
                                              Perm error? → Shutdown
```

---

## Machine & Deploy

### Nuvola (Kraken DOGE/EUR — LIVE)
```bash
# Da locale (Windows):
cd /mnt/c/dev/alpha-omega-trading
bash deploy.sh --nuvola --live

# Manuale via SSH:
rsync -avz --exclude={__pycache__, .git, .env, *.log, venv} ./ sergio@nuvola:/home/sergio/denaro/
ssh sergio@nuvola "sudo systemctl restart denaro-kraken.service"
```

### MARCODG1 (Bybit SOL/USDT — SHADOW)
```bash
# Via nuvola jump-host:
bash deploy.sh --marcodg1 --live

# Manuale:
rsync -avz -e "ssh -J sergio@nuvola" ./ marco@MARCODG1:/home/marco/denaro/
```

### Monitoring
```bash
# Nuvola
ssh sergio@nuvola "journalctl -u denaro-kraken.service -f"
curl http://nuvola:8909/health
curl http://nuvola:8909/metrics

# MARCODG1
ssh -J sergio@nuvola marco@MARCODG1 "journalctl -u denaro.service -f"
```

---

## Configurazione (`.env`)

```ini
# === Kraken API ===
KRAKEN_API=<api-key>
KRAKEN_SECRET=<api-secret>
SYMBOL=DOGE/EUR
CAPITAL=100

# === Mode ===
SHADOW_MODE=1          # 0 = LIVE trading
SHADOW_FACTOR=0.10

# === Risk Management ===
MAX_DAILY_LOSS_PCT=2.0
MAX_DRAWDOWN_PCT=5.0
MAX_CONSECUTIVE_LOSSES=4

# === Cache (v5) ===
BALANCE_CACHE_TTL=15   # Balance refresh ogni 15s
ORDERS_CACHE_TTL=10    # Orders refresh ogni 10s

# === Lockout Protection (v5) ===
LOCKOUT_BACKOFF_MIN=30
LOCKOUT_BACKOFF_MAX=600

# === Telegram ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## v5 Lessons Learned (from production)

1. **Balance caching è ESSENZIALE** — senza, Kraken lockout dopo ~100 chiamate/min
2. **Invalid key detection** — ferma subito, non prova a ritentare (Kraken + Bybit)
3. **Lockout backoff esponenziale** — 30s iniziali salvano da escalation
4. **Deep sleep mode** — evita hammering quando Kraken è down
5. **WS ticker è inaffidabile** — REST fallback deve essere sempre pronto
6. **Cache TTL configurabile** — 15s per balance, 10s per orders è il sweet spot
7. **Risk limits da .env** — MAX_DRAWDOWN_PCT di default era 15% (troppo alto!)
8. **Stato persistente** — denaro_core_state.json salva tutto, recovery automatico

---

## Versioni

| Versione | Periodo | Strategia | Stato |
|----------|---------|-----------|-------|
| v3 Grid | Giu 2026 | Grid trading puro | ARCHIVIATO |
| v6 Nuvola | Giu-Lug 2026 | Nuvola cloud orchestration | ARCHIVIATO |
| WAR Engine | Giu 2026 | News/reactor, whale tracking | ARCHIVIATO |
| **v6 Denaro** | **Lug 2026 →** | **Grid + caching + lockout + CB auto-recovery** | **LIVE** ✅ |

---

*Sergio Grivetto & CodeWhale AI — Luglio 2026*
