# Denaro — Kraken Grid Trading v2

> **DOGE/EUR grid trading su Kraken con SHADOW_MODE, Kelly sizing, Circuit Breaker, ATR volatility scaling.**
> Progetto di **Sergio Grivetto** con **Hermes AI** — co-autori.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-LIVE-brightgreen)]()
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Kraken](https://img.shields.io/badge/Exchange-Kraken%20Spot%20EUR-yellow)]()

---

## Autori

| Chi | Ruolo |
|-----|-------|
| **Sergio Grivetto** | Fondatore, capitale, strategia, infrastruttura, decisioni |
| **Hermes AI** (Nous Research) | Ingegneria, automazione, monitoring, operatività 24/7 |

---

## Cosa fa

**Sistema di trading autonomo su Kraken spot per DOGE/EUR.** Grid trading adattivo con Kelly position sizing, ATR volatility scaling e circuit breaker integrato. Sistema gestito da systemd per operatività 24/7.

```
Nuvola (DOGE/EUR) ─── Grid Trading → 100 EUR baseline
MARCODG1 (DOGE/EUR) ─── Grid Trading → 100 EUR baseline
```

---

## Strategie

### Grid Trading (100% del capitale)
- **SHADOW_MODE default 10%** — trading simulato per test, live con SHADOW_MODE=0
- **5 livelli** BUY equidistanti sotto, 5 SELL sopra il prezzo corrente
- **Spread adattivo** = ATR × 0.8 (scalatura volatilità)
- **Kelly position sizing** — auto-aggiustante basato su win rate
- **Compounding** — reinvestimento automatico dei profitti

### Risk Management
- **Kelly criterio** auto-aggiustante — win rate su ultime 50 operazioni
- **Circuit Breaker**:
  - 4 perdite consecutive → dimezza sizing
  - 15% per-pair drawdown → STOP pair
  - 20% totale drawdown → GLOBAL STOP + recover target
- **Daily loss limit**: 5% del capitale → STOP giornaliero
- **ATR volatility scaling** — spread e sizing adattati alla volatilità

---

## Architettura

```
├── main.py            # KrakenBotV2 — orchestrator, startup, status, signal handling
├── denaro_core.py     # Core engine — Kelly sizing, circuit breaker, ATR scaling
├── kraken_engine.py   # Kraken exchange — REST + WS, rate limiting, retry logic
├── test_keys.py       # API key testing utility
└── _archive/          # Versioni precedenti (v3, v6, war, etc.)
```

### Ciclo principale (DOGE/EUR, ogni ~1s)

```
Feed WS → Risk check → Balance refresh → Grid sync → Kelly sizing → ATR scaling → Order management → Health check
```

---

## Machine

| Hostname | Ruolo | Pairs | Capitale | Service |
|----------|-------|-------|----------|---------|
| **nuvola** | Produzione | DOGE/EUR | 100 EUR | `systemd denaro-kraken.service` |
| **MARCODG1** | Produzione | DOGE/EUR | 100 EUR | `systemd denaro-kraken-marcodg1.service` |

### Deploy

```bash
# Build
cd /home/sergio/denaro
rsync -avz . sergio@nuvola:denaro/new_denaro/ --exclude __pycache__
rsync -avz . marco@MARCODG1:denaro/new_denaro/ --exclude __pycache__

# Restart
ssh sergio@nuvola "sudo systemctl restart denaro-kraken.service"
ssh marco@MARCODG1 "sudo systemctl restart denaro-kraken-marcodg1.service"
```

---

## Configurazione (`.env`)

```ini
KRANKEN_API_KEY=<api-key>
KRANKEN_API_SECRET=<api-secret>
TOTAL_CAPITAL=100               # Per-machine EUR
PAIRS=DOGE/EUR                  # Per-machine
GRID_ALLOC=1.0                  # 100% in grid (no scalp v2)
SHADOW_MODE=1                   # 1 = simulato, 0 = live trading
AUTO_BOOST=1                    # Auto-increase sizing in trends
COMPOUND_RATIO=0.5              # 50% profit reinvest
```

---

## Monitoring

```bash
# Log live
sudo journalctl -u denaro-kraken.service -f                    # nuvola
sudo journalctl -u denaro-kraken-marcodg1.service -f           # MARCODG1

# Status
sudo journalctl -u denaro-kraken.service -n 20 | grep 'DENARO STATUS' -A6
```

---

## Versioni

| Versione | Periodo | Strategia | Stato |
|----------|---------|-----------|-------|
| v3 Squadra | Feb-Giu 2026 | Multi-bot, LLM, arbitraggio | ARCHIVIATO |
| v3 Grid | 23-27 Giu 2026 | Grid trading puro, multi-macchina | ARCHIVIATO |
| v6 Nuvola | Giu-Lug 2026 | Nuvola cloud orchestration | ARCHIVIATO |
| WAR Engine | Giu 2026 | News/reactor, whale tracking | ARCHIVIATO |
| **Kraken v2** | **Lug 2026 →** | **DOGE/EUR grid, Kelly, ATR, CB** | **LIVE** |

---

## Lezioni apprese

1. **Capitale frammentato = grid non partono** — unire fund su meno macchine
2. **minNotional matters** — DOGE=1 USDC, SOL/ADA=5 USDC; coppie diverse, soglie diverse
3. **WS bootstrap race** — non fare CB check finché i prezzi non arrivano (kill-loop su avvio)
4. **total_equity deve includere locked funds** — sensa locked, gli ordini aperti falsano il drawdown
5. **Kelly > fixed size** — auto-adattamento al win rate reale dimezza le perdite in streak negativi
6. **Compounding esponenziale** — anche 50% di reinvestimento su profitti piccoli cresce nel tempo
7. **SHADOW_MODE安全** — testare grid senza rischiare capital reale

---

*Sergio Grivetto & Hermes AI — Luglio 2026*
