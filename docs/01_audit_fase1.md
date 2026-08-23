# DENARO — Audit Architetturale Fase 1 (2026-08-23)

> Deliverable della Fase 1 del piano di riprogettazione enterprise (Audit → Blueprint → Implementazione).
> Nessun codice è stato modificato in questa fase: solo lettura di codice, ispezione delle macchine remote
> e misurazione del drift tra repo e runtime.

---

## 0. Sintesi esecutiva

Il sistema **funziona** (4 bot live + 3 paper, dashboard, Zabbix), ma è costruito su una **baracca non supervisionata**:

| # | Criticità | Severità | Impatto |
|---|-----------|----------|---------|
| C1 | **Doppio bot Kraken su nuvola** (legacy 15€ + v3.3 25€, stesso conto, stesso symbol SOL/EUR) | 🔴 CRITICO | Due grid indipendenti sullo stesso conto: stati interni divergenti, ordini in conflitto, accounting corrotto. Attivo da >5 ore. |
| C2 | **Nessuna supervisione dei processi** (nessun systemd: processi `nohup`-style, no restart su crash/reboot) | 🔴 CRITICO | Un reboot di MARCODG1 spegne tutto il trading senza riaccenderlo. |
| C3 | **Il motore live NON ha risk management** (`risk.py` esiste ma è codice morto/rotto, mai importato) | 🔴 CRITICO | Nessun circuit breaker, nessun daily loss limit, nessuno stop drawdown: il drawdown è solo *misurato* (health), mai *azionato*. |
| C4 | **8 file su 14 in `denaro/` sono morti e NON importabili** (import di moduli inesistenti: `indicators`, `dca`, `micro`, `state`, `exchange`, `kraken_engine`, `VolatilityRegime`) | 🟠 ALTO | Il layer v6/v7 "sembra" implementare risk/regime/grid avanzato ma è un miraggio: inganna la manutenzione e nasconde l'assenza reale di risk management. |
| C5 | **Codice operativo NON versionato** (`zabbix/push_metrics.py`, `fetch_kraken_snapshot.sh`, `~/zabbix_bot_metrics.sh`, `kraken_snapshot.py` su nuvola) | 🟠 ALTO | Il monitoraggio gira con codice fuori dal repo: il repo non è la fonte di verità dell'intero sistema. |
| C6 | **Drift di deploy**: `health_server_v33.py` in esecuzione su MARCODG1 è una variante VECCHIA (diversa dal repo); `/home/marco/denaro` contiene 38 file, molti relitti dell'era pre-consolidamento | 🟠 ALTO | Configurazioni e servizi documentati nel repo non corrispondono alla realtà runtime. |
| C7 | **Re-grid non idempotente nel motore live** (`engine_solo_v33.py:322-324` + `_place_grid`) | 🟠 ALTO | Dopo un fill, ri-piazza l'intera griglia senza cancellare i buy residui → sovraesposizione o ordini rifiutati; ordini stantii mai cancellati → capitale congelato. |
| C8 | **Latenza e carico REST**: polling 60s, ~8-10 chiamate REST per tick per bot, senza backoff esplicito; WebSocket esiste ma è nel codice morto | 🟠 ALTO | Latenza ordini fino a 60s; prossimità ai rate limit OKX con più bot. |
| C9 | **PnL non persistito in modo robusto**: `total_profit` in memoria (riparte da 0 a ogni riavvio), `pnl_log.jsonl` è append-only mai riletto, `entry_price` dei sell stimato con `price*0.99` | 🟡 MEDIO | I numeri di PnL/equity su dashboard e Zabbix non sono riconciliabili con la storia reale. |
| C10 | **Sicurezza**: Zabbix `Admin/zabbix` default; dashboard pubblica su `mgrivett.ddns.net` senza auth verificata; CORS `*` su `infra.json` | 🟡 MEDIO | Esposizione di dati finanziari e controllo del monitoring. |
| C11 | **`types.py` oscura lo stdlib `types`** se il package viene messo su `sys.path` (test locale: TUTTI gli import falliscono) | 🟡 MEDIO | Footgun latente: oggi nessuna macchina ha `types.py` nella dir di deploy; basterebbe una copia per rompere tutto. |
| C12 | `datetime.utcnow()` deprecato; log non strutturati; `except Exception` pervasivo con fallimenti silenziosi | 🟡 MEDIO | Qualità e diagnosi. |

**Verdetto**: il codice del motore (v3.3) è pragmatico e funzionante — merita di essere **consolidato, non riscritto** (lezione delle 7 riscritture). Ma la *macchina* che lo circonda (deploy, supervisione, risk, persistenza, monitoraggio versionato) è a livello di prototipo. La Fase 2 (Blueprint) deve trasformare **l'infrastruttura attorno al motore**, non il motore.

---

## 1. Verità di terreno: cosa gira dove (rilevato il 23/08/2026)

### 1.1 MARCODG1 (87.106.222.123) — bot OKX + infra

| Processo | Comando | Note |
|----------|---------|------|
| Bot ADA/EUR | `engine_solo_v33.py --exchange okx --symbol ADA/EUR --capital 20.0 --profit-target 2.0 --buy-distance 0.1 --grid-levels 3 --loop --interval 60 --health-file .../health/ada.json` | PID attivo. **`--buy-distance 0.1` ≠ repo (unità dice 1.5)** |
| Bot SOL/EUR | `engine_solo_v33.py --exchange okx --symbol SOL/EUR --capital 5.0 --profit-target 1.5 --buy-distance 1.0 ...` | PID attivo |
| Paper ADA/SOL/XRP | `engine_paper.py` (300/100/100€) | 3 processi attivi |
| Health server | `health_server_v33.py` — **variante VECCHIA** (docstring "Alpha-Omega Health Server - espone stato bot via HTTP", senza endpoint `/health/<bot>`) | Diverso dal repo |
| Infra aggregator | `infra_aggregator.py` :8912 | Attivo |
| Snapshot cron | `infra_snapshot.py` ogni minuto (cron) | Attivo |
| Push Zabbix | `zabbix/push_metrics.py` ogni minuto (cron) + `~/zabbix_bot_metrics.sh` | NON versionati |
| Kraken snapshot | `fetch_kraken_snapshot.sh` ogni minuto (cron) | NON versionato |

**Nessuno di questi processi è sotto systemd** (verificato: `systemctl list-units` mostra solo `docker.service`). Le unit nel repo (`systemd/*.service`) **non sono installate** su MARCODG1.

### 1.2 nuvola (87.106.3.15) — bot Kraken

| Processo | Comando | Note |
|----------|---------|------|
| ⚠️ Bot LEGACY | `python -m alpha_omega.core.engine_solo --exchange kraken --symbol SOL/EUR --capital 15.0 ...` | PID 211462, attivo da 16:09 (5h+). **DA UCCIDERE** |
| Bot v3.3 | `engine_solo_v33.py --exchange kraken --symbol SOL/EUR --capital 25.0 ... --health-file .../health/sol_kraken.json` | PID 239291, attivo da 20:35 |

**C1 (CRITICO)**: due motori indipendenti girano sullo **stesso conto Kraken**, stesso symbol `SOL/EUR`, con due stati separati (15€ e 25€). Il vecchio processo non è mai stato terminato quando è stato deployato il nuovo. Conseguenze: entrambi piazzano ordini grid sullo stesso pair; ciascuno calcola il proprio saldo "libero" ignorando l'altro; i fill dell'uno non sono noti all'altro → posizioni e PnL interni divergono dalla realtà. Va ucciso il PID 211462 e verificata la riconciliazione degli ordini aperti.

### 1.3 mc2 (192.168.1.99) — Zabbix server (Docker)

Nessun bot trading; host Zabbix (7 host Denaro, 75 item, trigger) + tunnel SSH inverso da MARCODG1 (autossh `-R 10051 -R 1080`).

---

## 2. Drift repo ↔ macchine (misurato con hash)

| File | MARCODG1 | nuvola | Esito |
|------|----------|--------|-------|
| `engine_solo_v33.py` | `c0b1a069…` | `c0b1a069…` | **Identico al repo** (diff EOL-insensitive: 0 righe) ✅ |
| `engine_paper.py` | `1cd9b4dd…` | — | **Identico** ✅ |
| `infra_aggregator.py` | `5538e64e…` | — | **Identico** ✅ |
| `infra_snapshot.py` | `01805aa2…` | — | **Identico** ✅ |
| `health_server_v33.py` | `29e8da17…` | — | **DIVERSO**: il remoto è una variante più vecchia (40 righe diverse) ❌ |

Inoltre `/home/marco/denaro` contiene **38 file `.py`** (relitti: `airdrop-farm/`, `alpha_omega/`, `enhanced/`, `docker/`, `denaro_zabbix.py`, `mexc_engine.py`, `bybit_engine.py`, `risk_manager.py`, service file obsoleti, script `_*.py` diagnostici) contro i 14 file del repo consolidato. Il **repo è la fonte di verità solo per 4 file su 5**; il resto della baracca vive sulla macchina senza versionamento.

---

## 3. Audit per modulo (citazioni file:riga)

### 3.1 `engine_solo_v33.py` — il motore live (436 righe, monolite auto-contenuto)

**Positivo (da preservare nel blueprint):**
- Capitale effettivo = `min(capital, free)` (`:278`) — corretta gestione del capitale limitato.
- Scrittura health **atomica** (tmp + `os.replace`, `:356-359`) — pattern da estendere a tutto lo stato.
- Endpoint EEA obbligatorio per OKX (`:80-83`) — fix storico corretto.
- Precisione mercato da `load_markets` (`:156-171`).
- Zero dipendenze oltre ccxt + dotenv — facile da deployare.

**Difetti (severità → impatto):**

| Rif. | Problema | Impatto |
|------|----------|---------|
| `:322-324` + `:271-309` | **Re-grid non idempotente**: se `free_eq >= per_level_needed` e `len(open_buys) < grid_levels`, ri-piazza l'INTERA griglia senza cancellare i buy residui | Sovraesposizione (open_buys può superare grid_levels), ordini rifiutati dall'exchange per saldo, comportamento non deterministico |
| — (assente) | **Nessuna cancellazione di ordini stantii**: un buy mai riempito (market salito) resta per sempre; nessun retarget | Capitale congelato in ordini morti; il bot smette di fatto di tradare senza segnalarlo |
| — (assente) | **Nessun risk management**: nessun circuit breaker, daily loss limit, max drawdown *azionato*, position sizing, Kelly (esiste in `risk.py` ma è morto, §3.3) | In un dump il bot continua a comprare finché la griglia non è piena; nessuna protezione attiva |
| `:202` | `entry_price = price * 0.99` per i sell ricostruiti al riavvio | PnL stimato con ipotesi arbitraria -1%; `total_profit` non riconciliabile |
| `:140-141, 238` | `total_profit`/`total_trades`/`wins`/`losses` **solo in memoria**; `log_pnl` (append-only) mai riletto al boot | Ogni riavvio azzera le metriche; la storia vera è nel log ma il motore non la usa |
| `:209-260` | `check_orders` fa 1 `fetch_order` per ordine per tick (N+1); errori transitori → `log.debug` e passa, **senza retry/backoff** | ~7-10 chiamate REST per tick per bot; ordine perso silenziosamente se l'API fallisce |
| `:42-51` | `tg_send` **sincrono** nel loop a ogni evento (timeout 10s) | Un evento Telegram può bloccare il tick fino a 10s; a ogni fill multiplo il loop rallenta |
| `:222, 252, 354` | `datetime.utcnow()` deprecato (3.12) | Warning; futuro removal |
| `:28-32` | Log non strutturato (formato piatto, stdout) | Diagnosi multi-bot/multi-macchina difficile |
| `:390-400` | `place_order` ritorna `None` su errore e il chiamante non ritenta né compensa | Livello di griglia non coperto in silenzio |
| `:154` | `__init__` invia Telegram e ricostruisce stato → **dry-run con effetti collaterali** (`:420-436` costruisce `SoloEngine` completo) | Dry-run manda messaggi e chiama API di lettura |

### 3.2 `engine_paper.py` (219 righe)

- `:90` `_save_state` con `write_text` **non atomico** → crash a metà scrittura = file corrotto; `:110` `except Exception: pass` su load → stato perso silenziosamente. (Il motore live ha già il pattern tmp+rename; il paper non lo usa.)
- Nessun retry/backoff su `fetch_ticker` (`:196-197`).
- PnL stimato per inversione (`:150` `cost_orig = amount * (price/(1+tp)) * (1+FEE)`) — ok per paper, non riusabile per il live.
- **Utile**: è la base del backtesting forward (prezzi reali, fill simulati). Va conservato e reso deterministico (seed, clock iniettabile) per la Fase 2.

### 3.3 Layer v6/v7 — `core.py`, `risk.py`, `types.py`, `regime_enhanced.py`, `grid_enhanced.py`, `dynamic_grid.py`, `indicators_advanced.py`, `multi_exchange.py`, `okx_engine.py`

**Verdetto: 8 file su 9 sono DEAD CODE NON IMPORTABILE.** Verifica empirica (import test):

| Modulo | Esito | Causa |
|--------|-------|-------|
| `risk.py` | ❌ ImportError | `from . import indicators` — `indicators.py` NON esiste in `denaro/` |
| `core.py` | ❌ ImportError | `from .dca/.micro/.state import …` — moduli inesistenti |
| `multi_exchange.py` | ❌ ImportError | `from .exchange/.kraken_engine import …` — inesistenti |
| `okx_engine.py` | ❌ ImportError | `from .exchange import ExchangeAdapter` — inesistente |
| `regime_enhanced.py` | ❌ ImportError | `from . import indicators` — inesistente |
| `grid_enhanced.py` | ❌ ImportError | `from . import indicators` + `from .types import VolatilityRegime` — `VolatilityRegime` NON è definito in `types.py` |
| `dynamic_grid.py` | ❌ ImportError | `from .indicators import atr_percent, volatility_regime` — inesistente |
| `indicators_advanced.py` | ✅ importabile | dipende solo da `types` (esiste) |
| `types.py` | ✅ importabile | ma incompleto (manca `VolatilityRegime`) |

I moduli mancanti esistono solo in `legacy/` (`legacy/neo/exchange.py`, `legacy/alpha_omega/core/state.py`, `legacy/alpha_omega/strategies/dca.py`, ecc.) — il layer v6/v7 è un **fossile estratto dalle riscritture abbandonate**, rimasto nel repo dopo il merge conflict resolution (commit `8a5fa4c`/`832d745`).

**Conseguenza architetturale fondamentale (C3+C4)**: chiunque legga il repo vede `risk.py` con circuit breaker, Kelly, compounding, vol-scaling… e crede che il sistema abbia risk management. **Non è così**: il motore live non lo importa. Il gap tra "quello che il repo promette" e "quello che gira" è il difetto architetturale più grave.

Nota positiva: `okx_engine.py` contiene l'unica implementazione WebSocket del sistema (`ccxt.pro`, `_ws_main`, `_ws_watch_ticker`, `_ws_watch_orderbook`) — da **riusare** in Fase 2 (con `hostname=eea.okx.com`), non da buttare.

### 3.4 `health_server_v33.py` (repo, 74 righe)

- Pulito e minimale; endpoint `/health` e `/health/<bot>`.
- **Il processo in esecuzione su MARCODG1 è un'altra versione** (senza `/health/<bot>`). Da allineare.
- `read_health` con `except: None` → 404 silenzioso; manca indicatore di "stale" (un health file vecchio di 10 minuti è servito come "running").

### 3.5 `infra_aggregator.py` / `infra_snapshot.py` (315+87 righe)

- **Snapshot pre-generato** + cache TTL = la dashboard risponde in ~0.02s: soluzione pragmatica corretta ✅ (da mantenere).
- SSH via `bash -c` + subprocess nel path dati (`:58-81`): fragile (dipende da config ssh, `BatchMode`, timeout 15-25s), fallisce silenzioso → `None`. Nel fallback *live* di `/infra.json` un host giù costa 5-25s di attesa.
- `fetch_okx_balance` crea un **nuovo client ccxt a ogni cache-miss** (`:96-102`) — costoso; e legge chiavi da path hardcoded su MARCODG1 (`ENV_FILES`, `:31-34`).
- NODES/ENV_FILES hardcoded → accoppiamento al deployment specifico.
- Cache senza lock (ok oggi perché `HTTPServer` è single-threaded; **pericolo se si passa a ThreadingHTTPServer**).
- CORS `*` (`:271`) + payload con saldi/path: accettabile solo perché ascolta su 127.0.0.1; va rivisto se esposto.
- `infra_snapshot.py` duplica la logica di `collect()` dell'aggregator via import del modulo (`:12-18`) — copia quasi letterale (`collect()` vs `build()`), da unificare in Fase 2 (DRY).

### 3.6 Config

- `config/strategy_config_marcodg1.json`, `config/fleet_config_marcodg1.json`, `fleet_config_nuvola.json` — **reliquie morte** dell'era fleet (BICO/GRVT/USDT, "Trading disabilitato", 12/08): non usate da nessun processo live. → `legacy/` in Fase 2.
- I parametri reali dei bot (capital, buy-distance, TP, interval, health-file) vivono **nei comandi dei processi**, non in un config file → la configurazione non è versionata né riproducibile.

---

## 4. Flusso dati reale (mappato)

```
[engine_solo_v33 (ADA/SOL OKX @MARCODG1)]  ──atomic write──▶ health/{ada,sol}.json
[engine_solo_v33 (KRAKEN @nuvola)]          ──cron scp─────▶ health/kraken_snapshot.json  (fetch_kraken_snapshot.sh)
[engine_paper (×3 @MARCODG1)]               ──write────────▶ paper_state/*.json
        │
        ▼ (cron 1min)
infra_snapshot.py ──▶ health/infra_snapshot.json ──▶ infra_aggregator :8912 ──▶ dashboard web (nginx https)
        │                                                                        ▶ Zabbix push (cron 1min, 77 valori)
```

Colli di bottiglia:
1. **Polling 60s** → latenza ordini 0-60s (per grid TP 1.5-2% è tollerabile, non enterprise).
2. **N+1 REST** nel tick (1 ticker + N fetch_order) → volume di chiamate e rischio rate-limit.
3. **PnL/equity non riconciliabili** tra engine, aggregator e Zabbix (fonti di verità diverse, nessuna riconciliazione).

---

## 5. Sicurezza

| Rischio | Stato | Azione |
|---------|-------|--------|
| Chiavi API in `.env` (OKX main, marcosub1, Kraken) | Non tracciate in git ✅; permessi file da verificare | Verifica `chmod 600` |
| Zabbix `Admin/zabbix` (password default) | ❌ | Cambiare password + limitare IP |
| Dashboard pubblica `https://mgrivett.ddns.net/dashboard/` | Espone saldi/equity/path; auth nginx **non verificata** | Verificare/integrare auth (basic o token) |
| `infra.json` CORS `*` | Mitigato da bind 127.0.0.1 | Non esporre oltre localhost |
| `types.py` shadowing stdlib | Footgun latente (rompe TUTTI gli import se messo su sys.path) | Rinominare in `state_types.py` o spostare in package |
| Git history | Nessun `.env` trovato ✅ | — |

---

## 6. Raccomandazioni prioritarie (input per la Fase 2 — Blueprint)

**Immediate (non richiedono blueprint, vanno fatte subito):**
1. **Uccidere il bot legacy su nuvola** (PID 211462) e riconciliare gli ordini aperti Kraken SOL/EUR.
2. **Installare unit systemd vere** per tutti i bot su MARCODG1 e nuvola (con `Restart=always`, EnvironmentFile) — i processi attuali muoiono al reboot.
3. **Allineare `health_server_v33.py`** al repo e riavviarlo.
4. **Cambiare password Zabbix**; verificare auth dashboard.

**Per il Blueprint (Fase 2):**
5. **Versionare TUTTO il codice operativo** (`zabbix/push_metrics.py`, `fetch_kraken_snapshot.sh`, `kraken_snapshot.py`) e parametri bot in un config versionato.
6. **Integrare il risk management nel motore live**: portare (riparando) `risk.py` + `types.py` nel path live — circuit breaker con daily loss, max drawdown *azionato*, sizing; il motore v3.3 resta il nucleo, il risk diventa un layer intorno.
7. **Persistenza robusta**: stato atomico (pattern tmp+rename già in `_write_health`) + journal immutabile dei trade riletto al boot per ricostruire `total_profit`; rimuovere la stima `price*0.99` (persistere `entry_price` reale al momento della fill).
8. **Re-grid idempotente**: cancellare i buy stantii prima di ri-piazzare; timeout sugli ordini; macchina a stati per livello.
9. **Ridurre latenza**: WebSocket (riusando `okx_engine.py` `_ws_main`) per i tick, REST solo per azioni; backoff/retry espliciti.
10. **Eliminare il dead code**: spostare i 8 moduli rotti in `legacy/` (o ripararli solo se il blueprint li richiede — vedi #6); rimuovere `config/*fleet*` e `strategy_config_*`.
11. **Rinominare `types.py`** per eliminare lo shadowing.
12. **Test minimi**: invarianti del motore (nessuna sovraesposizione, ordini mai > grid_levels, PnL riconciliabile) su `engine_paper.py` reso deterministico.

---

## 7. Fonti

- Codice: `denaro/` (14 file), `systemd/`, `config/` — repo @ `832d745`.
- Runtime: probe SSH su MARCODG1 (processi, hash, cron, systemd), nuvola (processi, hash, cron), hash incrociati con il repo locale.
- Import test: `python -B` su tutti i moduli `denaro/` (9/14 falliti).
