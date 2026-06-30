# Denaro — Autonomous Trading System

> **Grid + Scalp ibrido su Binance spot. Auto-adattivo, compounding, Kelly risk.**
> Progetto di **Sergio Grivetto** con **Hermes AI** — co-autori.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-LIVE-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Binance](https://img.shields.io/badge/Exchange-Binance%20Spot%20USDC-yellow)]()

---

## Autori

| Chi | Ruolo |
|-----|-------|
| **Sergio Grivetto** | Fondatore, capitale, strategia, infrastruttura, decisioni |
| **Hermes AI** (Nous Research) | Ingegneria, automazione, monitoring, operatività 24/7 |

---

## Cosa fa

**Sistema di trading completamente autonomo su Binance spot.** Ogni macchina esegue un processo indipendente con i propri pair e capitale. Le strategie si adattano in tempo reale alla volatilità, con compounding automatico dei profitti e Kelly-based position sizing.

```
Nuvola (DOGE/USDC) ─── Grid + Scalp → 75 USDC
MARCODG1 (ADA+SOL) ─── Grid + Scalp → 70 USDC
```

---

## Strategie

### Grid Trading (65% del capitale per pair)
- **5 livelli** BUY equidistanti sotto, 5 SELL sopra il prezzo corrente
- **Spread adattivo** = ATR × 0.8 (largo in alta volatilità, stretto in bassa)
- **Compounding**: 50% dei profitti della grid reinvestiti automaticamente
- **Livelli dinamici** — riduce il numero di livelli se il capitale è insufficiente

### Scalp Trading (25% del capitale)
- **Entry su order book imbalance**: LONG quando bid/ask ratio > 1.8, SHORT quando < 0.55
- **TP dinamico** = ATR × 1.5, **SL dinamico** = ATR × 0.8
- **Trailing stop** attivato al 50% del TP
- **Timeout** posizione a 180s

### Risk Management
- **Kelly criterio** auto-aggiustante — win rate su ultime 50 operazioni
- **Progressive circuit breaker**:
  - 4 perdite consecutive → dimezza sizing
  - 15% per-pair drawdown → STOP pair
  - 20% totale drawdown → GLOBAL STOP + recover target
- **Daily loss limit**: 5% del capitale → STOP giornaliero
- **Bootstrap safe**: CB non scatta finché tutti i prezzi WS non arrivano

---

## Architettura

```
denaro/
├── __init__.py        # entry doc
├── main.py            # DenaroApp — orchestrator, startup, status, signal handling
├── config.py          # Config dataclass, load_config() da env, helper adattivi
├── models.py          # Enums (CBState, Trend), dataclass (PairState, PerfState, AdaptiveState...)
├── exchange.py        # Exchange — REST + WS Binance, rate limiter, retry esponenziale
├── feeder.py          # Feeder — consuma WS data, calcola ATR, trend, volume spike, imbalance
├── grid.py            # GridEngine — livelli adattivi, compounding, anti-spam
├── scalper.py         # ScalpEngine — imbalance entry, trailing exit, Kelly sizing
├── risk.py            # RiskManager — Kelly auto-tuning, multi-level CB, compounding engine
└── loop.py            # TradingLoop — per-pair cycle: feed→risk→grid→scalp→capital→perf
```

### Ciclo principale (per pair, ogni ~1s)

```
Feed WS → Risk check → Balance refresh (30s) → Grid sync → Scalp tick → Capital update → Health write → Perf log
```

---

## Machine

| Hostname | Ruolo | Pairs | Capitale | Service |
|----------|-------|-------|----------|---------|
| **nuvola** | Produzione | DOGE/USDC | 75 USDC | `systemd denaro.service` |
| **MARCODG1** | Produzione | ADA/USDC, SOL/USDC | 70 USDC | `systemd --user denaro.service` |

### Deploy

```bash
# Build
cd /home/sergio/alpha-omega-trading
rsync -avz denaro/ sergio@nuvola:denaro/new_denaro/ --exclude __pycache__
rsync -avz denaro/ marco@MARCODG1:denaro/new_denaro/ --exclude __pycache__

# Restart
ssh sergio@nuvola "sudo systemctl restart denaro.service"
ssh marco@MARCODG1 "systemctl --user restart denaro.service"
```

---

## Configurazione (`.env`)

```ini
BINANCE_API_KEY=<sub-account-key>
BINANCE_API_SECRET=<sub-account-secret>
TOTAL_CAPITAL=75              # Per-machine
PAIRS=DOGE/USDC               # Per-machine
GRID_ALLOC=0.65
SCALP_ALLOC=0.25
SHADOW_MODE=1                 # 0 = scalp trading live
AUTO_BOOST=1                  # Auto-increase sizing in trends
COMPOUND_RATIO=0.5            # 50% profit reinvest
```

---

## Monitoring

```bash
# Log live
journalctl -u denaro.service -f                         # nuvola (sudo)
journalctl --user -u denaro.service -f                   # MARCODG1

# Status
ssh sergio@nuvola "sudo journalctl -u denaro.service -n 20 | grep 'DENARO STATUS' -A6"
```

---

## Versioni

| Versione | Periodo | Strategia | Stato |
|----------|---------|-----------|-------|
| v2 Squadra | Feb-Giu 2026 | Multi-bot, LLM, arbitraggio | ARCHIVIATO |
| v3 Grid | 23-27 Giu 2026 | Grid trading puro, multi-macchina | FERMO |
| **v3 Adaptive** | **30 Giu 2026 →** | **Grid+Scalp ibrido, Kelly, compounding** | **LIVE** |

---

## Lezioni apprese

1. **Capitale frammentato = grid non partono** — unire USDC su meno macchine
2. **minNotional matters** — DOGE=1 USDC, SOL/ADA=5 USDC; coppie diverse, soglie diverse
3. **WS bootstrap race** — non fare CB check finché i prezzi non arrivano (era kill-loop su avvio)
4. **total_equity deve includere locked funds** — senza locked, gli ordini aperti falsano il drawdown
5. **Kelly > fixed size** — auto-adattamento al win rate reale dimezza le perdite in streak negativi
6. **Compounding esponenziale** — anche 50% di reinvestimento su profitti piccoli cresce nel tempo

---

*Sergio Grivetto & Hermes AI — Giugno 2026*
