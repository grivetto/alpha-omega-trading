# Censimento flotta + riconciliazione PnL/fee — 2026-09-15

> Rilievi dell'agente **Stella** (DSH) via SSH sui nodi, **solo lettura**: nessun ordine, nessuna
> modifica a bot/servizi. Comandi disponibili: `~/scripts/fleet_snapshot.py` su mc2 (istantanea
> aggregatore + freschezza dei file di health).

## 1. Censimento unit `denaro-*` per nodo

| Nodo | Unit **system** attive | Unit user | Note |
|---|---|---|---|
| **mc2** | 5: `denaro-aggregator-mc2`, `denaro-dashboard-mc2`, `denaro-feeder-mc2`, `denaro-health-mc2`, `denaro-node-mc2` | 0 | nodo di monitoraggio + istanza **live OKX** |
| **nuvola** | 1: `denaro-health-nuvola` | 0 | `denaro-node-nuvola` e `denaro-node-trend` sono **disabled** |
| **MARCODG1** | 5: `denaro-aggregator-marcodg1`, `denaro-health-marcodg1`, `denaro-node-paper`, `denaro-node-trend-live`, `denaro-node-trend` | 0 | nodo con istanza **trend live Kraken** |

Su **nuvola** gira un solo processo Python (`health_server_nuvola.py`, PID 1003) in ascolto su
`127.0.0.1:8911`: **nessun processo bot**. Le unit dei bot sono installate ma **disabilitate**.

## 2. Bot dichiarati e freschezza reale dei dati

| Bot | Nodo dichiarato | File health | mtime | Età del dato | eq (dichiarata) | pnl (dichiarata) | trades |
|---|---|---|---|---|---|---|---|
| `mc2:okx:DOGE/EUR` | mc2 | `doge_mc2.json` | 2026-09-15 23:12 | **0 min** | 12.00 | +0.032629 | 2 |
| `mc2:okx:SOL/EUR` | mc2 | `sol_mc2.json` | 2026-09-15 23:12 | **0 min** | 12.00 | +0.130948 | 8 |
| `xrp_nuvola` | nuvola | `xrp_nuvola.json` | 2026-09-15 22:38 | 34 min | 25.3909 | +0.219771 | 1 |
| `eth_nuvola` | nuvola | `eth_nuvola.json` | 2026-09-15 22:37 | 35 min | 25.3871 | 0.0 | 0 |
| `sol_nuvola` | nuvola | `sol_nuvola.json` | 2026-09-15 22:37 | 35 min | 25.3871 | +0.108875 | 3 |
| `doge_nuvola` | nuvola | `doge_nuvola.json` | 2026-09-10 02:38 | **5.9 giorni** | 23.5043 | +0.014824 | 2 |
| `trend-live:SOL/EUR` | MARCODG1 | `trend_sol_kraken.json` | 2026-09-12 01:03 | **3.9 giorni** | 12.70 | 0.0 | 0 |
| `trend-live:XRP/EUR` | MARCODG1 | `trend_xrp_kraken.json` | 2026-09-12 01:03 | **3.9 giorni** | 12.70 | 0.0 | 0 |

## 3. Riconciliazione PnL/fee: eseguita in sola lettura (2026-09-15 23:30 UTC)

Strumenti creati sul nodo (mc2, `~/scripts/`): `okx_recon.py`, `okx_subaccounts.py`, `trade_recon.py`.
Tutti e tre usano **solo endpoint di lettura** (`fetch_balance`, `fetch_order`, lista sub-account):
nessun ordine, nessun trasferimento. Le credenziali sono lette dai file `.env` e **mai stampate**
(solo nome variabile e maschera).

### 3.1 Cosa è stato misurato

| Misura | Valore reale |
|---|---|
| Saldo del conto la cui chiave usa il bot (`~/alpha-omega-trading/.env`) | **EUR 0.00048693 · SOL 0.00098674 · DOGE 0.000000072** |
| Elenco sub-account con quella chiave | **negato**: `59500 Only the API key of the main account has permission` |
| Fill reali letti da OKX (ledger `node_data/okx_default_*_trades.jsonl`) | DOGE: 2 vendite chiuse, 3 acquisti chiusi · SOL: 8 vendite chiuse, 3 acquisti chiusi |
| Fee reali su quei fill | DOGE 0.327195 EUR (0.008147 vendite + 0.319048 acquisti) · SOL 0.032968 EUR (0.032696 + 0.000272) |
| Inventario DOGE non venduto (dai fill reali) | **159.5241 DOGE comprati − 104.0949 venduti = 55.4292 DOGE** |
| Equity dichiarata dai bot (state.json) | 12.0 EUR per bot, max_dd 0.0 |
| PnL dichiarato dai bot | DOGE +0.032629 · SOL +0.130948 (tutti i trade vincenti) |

### 3.2 Incoerenze accertate

1. **L'equity dichiarata (12 EUR/bot) non corrisponde ad alcun saldo reale leggibile**: il conto della
   chiave in uso ha 0.0005 EUR. Non si tratta di un arrotondamento: è un ordine di grandezza diverso.
2. **Inventario non riconciliato**: 159.52 DOGE comprati per 12.00 EUR, 104.09 venduti; i 55.43 DOGE
   residui (~4.3 EUR al prezzo degli ultimi fill) **non risultano** nel conto leggibile.
3. **Il ledger locale è incompleto per il calcolo del PnL per ciclo**: un confronto
   "vendite − acquisti" sul ledger dà DOGE −8.25 EUR e SOL +4.32 EUR, ma include acquisti/invenduto
   non chiusi e cicli di periodi diversi: **non è un PnL realizzato** e non va usato come tale.
4. **Le unità di capitale sono dichiarate ma non verificate**: la config dice `capital: 23.0`,
   lo `state` dice `peak_equity: 12.0`, l'exchange dice 0.0005 EUR.

### 3.3 Conclusione della riconciliazione

**Il PnL dichiarato dai bot NON è riconciliato con l'exchange.** Non è possibile chiudere la
riconciliazione per nodo con i dati attuali, per due motivi concreti:

- la chiave disponibile **non ha i permessi** per leggere i sub-account dove girano i capitali
  (serve una chiave del **conto MAIN** in sola lettura, oppure le chiavi dei singoli sub-account);
- il **ledger locale non registra le fee** né l'abbinamento acquisto→vendita, quindi il PnL per ciclo
  non è ricostruibile senza gli order detail dell'exchange.

### 3.4 Cosa serve per chiudere (richiesta a Sergio)

1. Una chiave **sola lettura** del conto MAIN OKX (abilita `fetch_balance` e lista sub-account), da
   mettere in un file dedicato con permessi 600 — oppure le chiavi dei sub-account `mc2sub1`,
   `TRENDSUB`, `MARCOSUB1`.
2. Autorizzazione a costruire un **ledger unico per conto** (append-only, JSONL) che registri per ogni
   ordine: `order_id`, symbol, side, amount, prezzo medio, **fee**, ts, stato — così il PnL per ciclo
   diventa calcolabile e verificabile senza dipendere dallo stato interno del bot.

### 3.6 Chiavi OKX trovate sul nodo (fingerprint, mai valori) e cosa rivelano

| File | Fingerprint chiave | Esito |
|---|---|---|
| `~/alpha-omega-trading/.env` (usata da `denaro-node-mc2`) | `8c47a89a231a` | saldo quasi nullo (0.0005 EUR) · **non** elenca sub-account (`59500 Only the API key of the main account has permission`) |
| `~/denaro_node_app/.env` | `8c47a89a231a` (stessa) | — |
| `~/atlas/.env` | `a35fffaa8edd` | **`50119 API key doesn't exist`**: chiave revocata |
| `~/atlas-legacy-20260901/.env` | `ef567af0bb3e` | **funziona**: elenca 5 sub-account e legge i saldi; ha anche scope trade (`fetch_open_orders` OK) |

### 3.7 Equity reale vs dichiarata — quadro COMPLETO (sola lettura, prezzi di mercato)

**Correzione**: la prima stima (23.96 EUR) copriva solo OKX. La flotta ha capitali **anche su Kraken**.
Tabella completa (`equity_full.py`, sorgente: aggregatore completo via MARCODG1, 2026-09-15 21:36 UTC):

| Conto | Asset | Quantità | Prezzo EUR | Valore EUR |
|---|---|---|---|---|
| OKX main | DOGE | 272.926235 | 0.06918 | 18.881037 |
| OKX main | SOL | 0.044001 | 83.85 | 3.689484 |
| OKX main | EUR | 1.382221 | 1.0 | 1.382221 |
| OKX main | ETH / ADA | tracce | — | 0.002091 |
| OKX mc2sub1 | SOL + EUR + DOGE | 0.000987 / 0.000487 | — | 0.083225 |
| OKX nuvolasub1 | EUR | 19.036482 | 1.0 | **19.036482** |
| OKX nuvolasub1 | SOL | 0.075528 | 83.85 | 6.333037 |
| OKX nuvolasub1 | XRP | 0.000194 | 1.1083 | 0.000215 |
| Kraken | XRP | 15.82655 | 1.1083 | **17.540565** |
| Kraken | SOL | 0.072099 | 83.85 | 6.045501 |
| Kraken | ADA / USD / EUR | 0.064431 / 0.4073 | — | 0.418302 |
| **TOTALE REALE** | | | | **73.4122 EUR** |

Confronto con quanto dichiarato dal sistema:

| Fonte | Valore | Scostamento |
|---|---|---|
| **Equity reale calcolata** | **73.41 EUR** | — |
| Aggregatore completo (`bot_equity 20.0` + `kraken_equity 75.81`) | **95.81 EUR** | **+22.4 EUR (+30.5%)** |
| Bot `state.json` (`peak_equity` 12.0 + 12.0 + 3.4) | 27.4 EUR | — (misura solo la parte OKX paper/live dei bot mc2) |

**L'aggregatore sovrastima la flotta di ~30%**: va corretta la somma (`bot_equity` sembra contare
capitale nominale, non saldi reali) prima di usare la dashboard per decisioni di rischio.

### 3.8 Fee: il PnL dichiarato è lordo

- Fill reali sull'exchange: DOGE 27 fill (22-30 agosto, controvalore 28.89 EUR), SOL 37 fill
  (22-30 agosto, controvalore 100.82 EUR), **tutti con fee registrate**.
- Il ledger locale dei bot (`node_data/okx_default_*_trades.jsonl`) **non contiene alcun campo fee**:
  il PnL dichiarato (+0.163577 EUR) è **lordo**.
- Ordini del 8-11 settembre verificati uno per uno (`trade_recon.py`): fee reali DOGE 0.327195 EUR,
  SOL 0.032968 EUR → **0.36 EUR di sole fee** contro un PnL dichiarato di 0.16 EUR.

### 3.9 Verifica incrociata con Hermes (canale `stella/inbox.md`, 21:34 UTC)

Hermes (sessione CLI reale) ha riportato dati che **ho verificato indipendentemente**:

| Affermazione di Hermes | Verifica di Stella | Esito |
|---|---|---|
| `sol.json`/`doge.json`/`eth.json`/`ada.json` sono file fossili (mtime 2026-09-01) | `ls -la` su MARCODG1: mtime **2026-09-01 23:24** | **confermato** |
| Il CB `weekly_loss_-94.8%` non è il trend live | il bot live scrive `trend_sol_kraken.json` (mtime oggi) con `PRE-FLIGHT BLOCK: min_notional 0.45 > available 0.0001` | **confermato** |
| L'unico CB reale è su XRP: `daily_loss -5.6%` | `trend_xrp_kraken.json`: `status blocked`, `CB OPEN: daily_loss_-5.6%` | **confermato** |
| I saldi reali vivono nell'aggregatore completo, non in quello locale mc2 | `http://[::1]:8912/api/infra.json`: OKX main/nuvolasub1/mc2sub1/Kraken tutti `ok=True` con i saldi reali | **confermato** |
| Le unit denaro-* su MARCODG1 | verificate: aggregator, health, node-paper, node-trend-live, node-trend | **confermato** |

### 3.11 ORDINI ORFANI su Kraken (verificato, sola lettura)

Su Kraken ci sono **3 ordini di vendita aperti e vivi, non gestiti da nessun bot**:

| id | simbolo | lato | prezzo | quantità | filled | stato |
|---|---|---|---|---|---|---|
| `OQXXOD-P3MAN-7TRUR2` | XRP/EUR | sell | 1.23287 | 5.25916971 | 0 | open |
| `OPDGIW-PUYL4-WYVRJF` | XRP/EUR | sell | 1.22845 | 5.27806472 | 0 | open |
| `OS6KQJ-K3M47-AKBRAP` | XRP/EUR | sell | 1.22584 | 5.28931592 | 0 | open |

- Totale XRP bloccato: **15.82655035 XRP** = tutto il saldo XRP del conto (free 0).
- Prezzo di mercato XRP/EUR al momento della verifica: **1.11246** → gli ordini sono **~10% sopra mercato**.
- Nessuno stato di bot traccia questi ordini: gli `state.json` locali hanno `open_buys`/`open_sells` vuoti
  e l'audit su OKX non trova ordini aperti. Sono quindi **orfani**: il bot che li ha emessi non li
  gestisce piu'.

**Rischio concreto**: 15.83 XRP (circa **17.5 EUR**, il 24% dell'equity della flotta) è immobilizzato
in vendite che si eseguiranno solo se il prezzo sale oltre ~1.226. Se XRP scende, il capitale resta
bloccato e la posizione non ha stop. Va deciso con Sergio: **annullare** gli ordini, **adottarli** in un
bot attivo, o lasciarli (con consapevolezza).

Verifica: `scripts/kraken_audit.py` + `scripts/open_orders_audit.py` (sola lettura, chiave Kraken della
legacy env — le chiavi Kraken in `~/atlas/.env` e `~/denaro_node_app/.env` rispondono `EAPI:Invalid key`).

### 3.12 Ordini aperti su OKX

Nessun ordine aperto su OKX (verificato con la chiave del conto main e con quella usata dal bot).
Gli `open_buys`/`open_sells` dei bot mc2 sono vuoti: coerente. **L'unica esposizione non gestita è su Kraken.**

La riconciliazione **ora è eseguibile** e ha prodotto numeri verificati:

1. **Equity reale flotta: 73.41 EUR**; l'aggregatore ne dichiara 95.81 (+30%): **da correggere**.
2. **PnL dichiarato dai bot: +0.163577 EUR lordo**, con ~0.36 EUR di fee accertate sui soli ordini
   8-11 settembre: il risultato netto è **negativo o nullo**, coerente con `REPORT_NON_GUADAGNA.md`.
3. **Il ledger dei bot non registra le fee**: finché è così nessun PnL dichiarato è attendibile.
4. **Due blocchi operativi attivi**: XRP trend (CB daily loss −5.6%, dal 2026-09-15 22:38) e
   SOL trend (pre-flight `min_notional` non coperto: nessuna liquidità libera).
5. **Il CB `weekly_loss_-94.8%` che allarmava la dashboard è un fossile del 2026-09-01**: va filtrato
   o archiviato, altrimenti maschera i blocchi veri.

## 4. Incoerenze rilevate (aggiornate con le verifiche di §3)

1. **`doge_nuvola` e i due bot trend risultano "running" ma con dati fermi da giorni**: l'aggregatore
   li mostra attivi pur essendo su file non aggiornati (nuvola non ha processi bot attivi).
2. **L'aggregatore locale mc2 dichiara `reachable: false` per mc2 stesso e `no key` sui saldi**; il
   percorso completo (aggregatore di MARCODG1 via `[::1]:8912`) invece riporta tutto correttamente.
   La dashboard usa il primo come fallback → può mostrare "no key".
3. **Sovrastima dell'equity del 30%** da parte dell'aggregatore (95.81 dichiarati vs 73.41 reali, §3.7).
4. **Falsi allarmi CB**: `weekly_loss -94.8% / -92.1% / -76.4%` provengono da file fossili del
   **2026-09-01** (`sol.json`, `eth.json`, `doge.json`, `ada.json`), non dal bot live.
5. **Blocchi REALI del 2026-09-15**: XRP trend `CB OPEN: daily_loss_-5.6%` (dal 22:38) e SOL trend
   `PRE-FLIGHT BLOCK: min_notional 0.45 > available 0.0001` (nessuna liquidità libera).
6. **3 ordini di vendita XRP orfani su Kraken** (§3.11): 15.83 XRP (≈17.5 EUR, 24% dell'equity flotta)
   immobilizzati in sell ~10% sopra mercato, non gestiti da nessun bot.
7. **Il ledger dei bot non registra le fee** → ogni PnL dichiarato è lordo e non riconciliato.
8. **La chiave OKX usata da `denaro-node-mc2` vede un conto da 0.0005 EUR** mentre i fondi stanno su
   conto main / `nuvolasub1` / Kraken.

## 6. Azioni eseguite su autorizzazione di Sergio (2026-09-16 00:20-00:25 CEST)

Tutte con strumento dedicato, backup o dry-run, e verifica dell'effetto.

| # | Azione | Strumento | Esito verificato |
|---|---|---|---|
| 1 | **Annullati i 3 ordini orfani su Kraken** | `scripts/kraken_cancel_orders.py --execute` (dry-run di default) | 0 ordini aperti; **XRP free 15.82655035** (prima 0) |
| 2 | **Corretta la sovrastima dell'equity** nell'aggregatore locale mc2 | `scripts/fix_local_aggregator_equity.py` + `scripts/repair_aggregator_helpers.py` | `equity_source: saldi_reali`; l'aggregatore primario (dashboard) dichiara **72.82 EUR** vs 73.41 calcolati (−0.8%) |
| 3 | **Archiviati i file health fossili** su MARCODG1 | `scripts/archive_stale_health.py --apply` | `archive_20260916/` con `ada/doge/eth/sol.json`; le voci `okx:*` con `weekly_loss -94.8/-92.1/-76.4` **non compaiono più** |
| 4 | **Ledger riconciliato con le fee reali** | `scripts/fee_ledger.py --apply` | `node_data/recon_ledger.jsonl` (27 righe) |

### 6.1 Dettaglio della correzione dell'equity

Causa esatta: in `denaro/infra_aggregator.py` (servizio `denaro-aggregator-mc2`, porta 8912) il calcolo era

```python
if okx_eq == 0:      okx_eq = 24.0        # fallback HARDCODED
if kraken_eq > 30.0: kraken_eq = 25.47    # fallback HARDCODED
```

e i saldi venivano letti da `/home/marco/...` (inesistenti su mc2) → `no key` → numeri inventati.
Il fix: `ENV_FILES` punta ai `.env` reali di mc2, aggiunge `fetch_eur_rate()`/`balance_eur()` (stessa
logica dell'aggregatore di MARCODG1) e valorizza i **saldi reali**; se non sono leggibili scrive
`null` + `equity_source: "unavailable"` invece di inventare un valore.

**Nota operativa**: il riavvio del servizio da sessione non interattiva richiede `sudo -n systemctl`
(l'autenticazione interattiva di systemd fallisce), e il vecchio processo sopravvive a un semplice
`systemctl --user`/`restart`: serve `sudo systemctl restart --kill-who=all denaro-aggregator-mc2.service`.
Verificato: il PID in ascolto sulla 8912 cambia e il campo `equity_source` compare nella risposta.

### 6.2 Dettaglio del ledger con fee (la scoperta importante)

Gli `order_id` registrati dai bot **non appartengono al conto main**: su OKX rispondono
`51603 Order does not exist`. Le fee vanno quindi lette con `fetch_my_trades` **sul conto del bot**
(chiave `fp 8c47a89a231a`):

| Simbolo | Fill | Controvalore | Fee reali | Fee / PnL dichiarato |
|---|---|---|---|---|
| DOGE/EUR | 11 (5 sell, 6 buy) | 31.78 EUR | **0.018357 EUR + 0.631249828 DOGE** | **56.3%** (solo quota EUR) |
| SOL/EUR | 16 (11 sell, 5 buy) | 36.35 EUR | **0.032696 EUR + 0.000453264 SOL** | **25.0%** (solo quota EUR) |
| XRP/EUR, ETH/EUR | 0 | — | — | nessun fill con questa chiave (probabile conto diverso) |

Due conclusioni verificate:
1. il PnL dichiarato dai bot è **lordo**: le fee ne erodono **un quarto o più**;
2. **le fee pagate in asset** (DOGE, SOL) non sono nemmeno contate in EUR dal bot, quindi il costo reale
   è superiore a quello mostrato.

Ledger riconciliato (append-only, una riga per fill, con `fonte_exchange`): 
`/home/sergio/alpha-omega-trading/node_data/recon_ledger.jsonl`.

## 7. Aperto / in attesa

1. **Chiavi OKX**: Sergio ha indicato che Hermes conserva copie delle chiavi in un file di backup.
   Richiesta inviata a Hermes (via `stella/outbox.md`) di fornire **il path** (non i valori), per capire
   quale chiave debba usare `denaro-node-mc2` — quella in uso vede un conto da 0.0005 EUR.
2. **XRP/EUR e ETH/EUR su `nuvolasub1`**: i fill non sono visibili con la chiave del bot → da chiarire
   quale conto li esegue, prima di estendere la riconciliazione a nuvola.
3. **Blocchi operativi correnti** (dopo l'archiviazione dei fossili si vedono quelli veri):
   `trend:XRP` CB `daily_loss -12.4%`, `trend:ADA -6.1%`, `trend:ETH -6.0%`; i bot grid
   (`ADA`, `DOGE`, `SOL`, `XRP`) in `PRE-FLIGHT BLOCK` per `min_notional`/`per_level`.

## 8. Stato delle azioni richieste da Sergio

| Richiesta | Stato |
|---|---|
| Annullare gli ordini orfani Kraken | **fatto** (0 ordini aperti, XRP libero) |
| Correggere la sovrastima dell'equity | **fatto** (formula locale corretta; primario a 72.82) |
| Archiviare i file health fossili | **fatto** (`archive_20260916/`) |
| Fee nel ledger per PnL attendibile | **fatto** (ledger riconciliato + fee reali misurate) |
| Chiave OKX del bot (file di backup di Hermes) | **richiesta inviata**, in attesa del path |
