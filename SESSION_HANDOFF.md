# SESSION HANDOFF — Denaro v4 Production State
**Data:** 2026-07-06/07  
**Autore:** CodeWhale (DeepSeek v4)

---

## Stato Produzione

### nuvola (87.106.3.15 — sergio)
| Servizio | Pair | Modo | Grid | CB | Equity |
|----------|------|------|------|----|--------|
| `denaro-kraken.service` | **PEPE/EUR** 🐸 | LIVE | 5/5 ✅ | CLOSED ✅ | ~100.61€ |

Env: `CAPITAL=100, SPREAD=0.015, LEVELS=8, TAKE_PROFIT=0.02, COOLDOWN=20`

### MARCODG1 (87.106.222.123 — marco)
| Servizio | Pair | Modo | Grid | CB | Equity |
|----------|------|------|------|----|--------|
| `denaro-marcodg1.service` | **WIF/EUR** 🐕 | LIVE | 5/5 ✅ | CLOSED ✅ | ~100.61€ |

Env: `CAPITAL=100, SPREAD=0.015, LEVELS=5, TAKE_PROFIT=0.02, COOLDOWN=20`

### Nota capitale
**100€ totali su UN conto Kraken.** Entrambi i bot condividono lo stesso saldo. Ogni bot usa ~50€ effettivi (5 ordini × ~10€). Le due API keys sono diverse ma puntano allo stesso wallet Kraken.

---

## Dashboard Pubblica
**URL:** https://sgrivett.ddns.net/denaro/  
**Stats:** Aggiornate via cron ogni 5 min da `enhanced/update_dashboard.py`  
**Legge da:** `denaro_core_state.json` (locale nuvola) + SSH a MARCODG1 per stato remoto

---

## Repository Git
**Branch:** `v4-rewrite`  
**Origin:** https://github.com/grivetto/alpha-omega-trading/tree/v4-rewrite

### File critici
| File | Scopo |
|------|-------|
| `main.py` | Entry point orchestratore |
| `denaro_core.py` | Risk engine (Kelly, CB, VaR, ATR, regime) |
| `kraken_engine.py` | Kraken adapter (WS, REST, precision) |
| `notifier.py` | Telegram notifications |
| `enhanced/update_dashboard.py` | Stats updater per dashboard |
| `enhanced/health_server.py` | Health HTTP endpoint |
| `zabbix_status.py` → `denaro_zabbix.py` | Zabbix UserParameter provider |
| `neo/` | **Future architecture** — memory-first async bot (non in produzione) |

### Servizi systemd
```
nuvola:   /etc/systemd/system/denaro-kraken.service
MARCODG1: /etc/systemd/system/denaro-marcodg1.service
```
Entrambi con `MemoryMax=256M, OOMPolicy=kill, OOMScoreAdjust=500`

### Zabbix (MC2 — 192.168.1.99:2222)
- Docker: zabbix-server, zabbix-web (porta 1080), mariadb
- Template: "Denaro Grid Bot" con items v4
- Items: pnl, equity, kelly, atr, trend, cb, trades, running, health
- Vecchi items rimossi: ADA, SOL, USDC, svc.count

---

## Bug risolti in v4

| # | Bug | Fix |
|---|-----|-----|
| 1 | DOGE hardcoded nel fetch balance | `base_asset = SYMBOL.split("/")[0]` |
| 2 | Equity non contava asset residui | Aggiunto calcolo DOGE residuo nel equity |
| 3 | Doppio sizing multiplier | Kelly calcolato UNA VOTA sola in `position_size()` |
| 4 | DCA PnL errato | Usa `avg_entry_price` non `entry_price` |
| 5 | Kelly accumulato | Boost one-shot, non cumulativo |
| 6 | Grid buy base hardcoded 2% | Usa spread ATR da `grid_params` |
| 7 | save_state senza throttle | Max 1x/30s + atomic write |
| 8 | load_markets fragile | 3 tentativi + precision fallback |
| 9 | Env var mismatch | `.env.example` allineato a `KRAKEN_API` / `KRAKEN_SECRET` |

---

## Zabbix Agent Config

### nuvola (`/etc/zabbix/zabbix_agentd.conf.d/`)
```
denaro_grid.conf — v4 items (pnl, equity, kelly, atr, trend, cb, trades)
denaro.conf — running, health, error.count
```

### MARCODG1 (`/etc/zabbix/zabbix_agentd.d/`)
```
denaro_grid.conf — stessi items di nuvola ma path /home/marco/denaro/
```

---

## Monitoraggio
- **Health endpoint:** http://127.0.0.1:8909/health (su entrambe)
- **Zabbix:** http://192.168.1.99:1080 (Admin/zabbix)
- **Log:** `journalctl -u denaro-kraken.service -f` (nuvola)
- **Log:** `journalctl -u denaro-marcodg1.service -f` (MARCODG1)

---

## TODO / Prossimi passi
1. [ ] Depositare altri fondi per aumentare CAPITAL (500€ → 5-10€/gg)
2. [ ] Shadow-deployare `neo/` in parallelo per validazione
3. [ ] Aggiungere secondo conto Kraken per separare i 100€
4. [ ] Testare ETH/EUR o SOL/EUR come terzo pair
5. [ ] Completare autenticazione Kraken in `neo/exchange.py`
