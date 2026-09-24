# Configurazioni Denaro — tassonomia

Una config per ruolo. **Mai due config con lo stesso ruolo su host diversi.**
La regola operativa è: *un engine per conto, un conto per engine.*

| File | Stato | Host di esecuzione | Conto | Cosa fa |
|---|---|---|---|---|
| `node_mc2.yaml` | **LIVE** | mc2 (`denaro-node-mc2`) | OKX main (mc2) | Grid DOGE/EUR + SOL/EUR |
| `node_trend_live_kraken.yaml` | **LIVE** | MARCODG1 (`denaro-node-trend-live`) | Kraken (TRENDSUB) | Momentum SOL/EUR |
| `node.yaml` | **PAPER** | MARCODG1 (`denaro-node-paper`) | — | 5 bot paper (parità) |
| `node_trend.yaml` | **PAPER** | MARCODG1 (`denaro-node-trend`) | — | Momentum + adaptive paper |
| `node_paper.yaml` | **PAPER** | — | — | M6/M7 paper legacy |
| `node_nuvola.yaml` | **DISABLED** | — | OKX (chiavi non valide) | Tutti i bot `enabled: false` |
| `node_trend_live.yaml` | **TEMPLATE** | — | — | Bozza per sub-account OKX |
| `node_vagr_paper.yaml` | **LEGACY** | — | — | Strategia VAGR, non usata |
| `node_adaptive_vol_grid_paper.yaml` | **LEGACY** | — | — | AdaptiveVolGrid paper |

## Regole

1. **`enabled: true` significa denaro reale.** Ogni bot live deve avere un
   `health_path` e un conto dedicato. Due bot live sullo stesso conto
   riportano la stessa equity (doppio conteggio) e possono piazzare ordini
   duplicati.
2. **Il deploy deve essere identico al git.** Prima del 2026-09-15 le config
   in produzione divergevano dal repo (es. `node_trend_live_kraken.yaml`
   aveva XRP `enabled: true` in produzione e `false` nel repo).
3. **I backup non stanno nel repo**: sono in `.gitignore` (`*.bak.*`).
4. **Le chiavi stanno solo nel `.env`** della WorkingDirectory della unit —
   mai nel repo, mai in questa cartella.

## Chiavi operative

### `min_notional` (per bot)

Minimo d'ordine **dichiarato** per il symbol, in valuta di quotazione. È il
ripiego della *soglia operativa* del controllo di finanziamento quando
`min_notional(symbol)` dell'adapter non risponde (markets non caricate, venue
senza filtro `cost.min`). Sotto quella soglia il bot classifica il conto come
**NON FINANZIATO** (`capitale_stato: non_finanziato` in health), non piazza
ordini e **non** aggiorna peak/daily/weekly baseline: niente più tick saltati in
silenzio con "equity inattendibile".

```yaml
bots:
  - symbol: LINK/EUR
    mode: okx
    capital: 24.83
    min_notional: 1.0
```

Se manca sia dall'adapter sia da qui, si usa il default prudente **1 EUR** e
l'origine del numero viene dichiarata in health (`capitale_soglia_origine`:
`exchange` | `config` | `default`).

### `exposure_cap_notional` (di nodo o di bot)

Cap di **esposizione di conto** in nozionale (size × prezzo), cioè il tetto
sulla SOMMA degli impegni di tutti i bot che condividono il conto
(`mode` + `env_prefix`). Il cap del motore è per bot: senza questo, sette bot
sullo stesso conto sommano la propria esposizione e nessuno vede il totale.

```yaml
exposure_cap_notional: 120.0        # livello NODO: vale per tutti i bot
bots:
  - symbol: LINK/EUR
    exposure_cap_notional: 40.0     # livello BOT: vince su quello di nodo
```

- **assente o 0 = nessun cap** (comportamento storico invariato: nessun registro
  iniettato, nessun rifiuto);
- il cap è del **conto**: non esiste un opt-out per il singolo bot. Se due bot
  dello stesso conto dichiarano cap diversi si applica il **più basso** (e il
  nodo lo scrive nel log);
- quando il cap rifiuta un'apertura, il motivo finisce in `_last_error`
  (`cap esposizione di conto: headroom esaurito ...`) e nel journal
  (`exposure_cap_blocked`); cap, impegnato e headroom sono pubblicati in health
  (`exposure_cap_notional`, `exposure_impegnato`, `exposure_headroom`).

## Verifica dell'allineamento

```bash
python -m denaro.backtest --config config/<file>.yaml --days 90   # gate di validazione
bash scripts/check_fleet_drift.sh                                 # git vs deploy
```
