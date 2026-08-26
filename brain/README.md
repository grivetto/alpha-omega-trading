# Brain Alpha-Omega

Watchdog autonomo + Strategy Lab + ponte con Hermes AI. Gira su **MARCODG1**
(unico host con ssh verso nuvola e mc2) come `denaro-brain.service`.

## Ciclo (ogni ~60s)
1. **Watchdog** (`checks.py`): unit systemd, health dei bot, processi critici
   su tutte e 3 le macchine.
2. **Auto-healing** (`repair.py`): unit inattive o bot con health congelato
   (>180s) → `systemctl restart` dell'unit ospite. Rate-limit: cooldown 600s,
   max 3 riavvii/ora, log su `logs/repairs.jsonl`.
3. **Zabbix** (`zabbix_push.py`): push stato `brain.*` (status, bots_down,
   repairs_total, hermes_age) + creazione items/trigger (workaround itemid
   reale). Il repair lo fa il Brain stesso; Zabbix = visibilità/alert.
4. **Ponte Hermes** (`hermes_bridge.py`): ogni 30 min scrive il digest dello
   stato in `inbox.md` su mc2, invoca Hermes headless (`hermes -z`), legge
   `outbox.md`, logga in `logs/hermes_conv.md`.
5. **Strategy Lab** (`strategy_lab.py`): ogni 6h backtest del GRID BILATERALE
   + regime filter (ADX/ATR/EMA200) su OHLCV 1h reale (OKX EEA + Kraken).
   Top candidato per simbolo → PAPER (override), validazione 24h → LIVE o
   scarto. Registry su `config/strategies/registry.json`.
6. **Git**: registry + override committati e pushati (repo su MARCODG1).

## File
| File | Ruolo |
|---|---|
| `config.py` | macchine, unit, bot, soglie, Zabbix, Hermes |
| `checks.py` | raccolta stato |
| `repair.py` | riparazioni con rate-limit |
| `zabbix_push.py` | push Zabbix + items/trigger |
| `hermes_bridge.py` | inbox/outbox + `hermes -z` + Telegram |
| `strategy_lab.py` | OHLCV, indicatori, backtest, registry |
| `main.py` | loop principale |

## Operazioni manuali
- Un ciclo singolo: `python -m brain.main --once`
- Log: `journalctl -u denaro-brain -f`
- Stato: `cat brain/data/brain_state.json`
- Riparazioni: `tail brain/logs/repairs.jsonl`

## Nota onesta
Il backtest è un modello 1h semplificato (fill ai livelli limite, fee
esplicite, slippage 0.05%): serve a RANKING dei parametri, non a predire il
profitto. La validazione vera è il PAPER 24h prima di ogni promozione a LIVE.
