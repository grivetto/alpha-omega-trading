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

## Verifica dell'allineamento

```bash
python -m denaro.backtest --config config/<file>.yaml --days 90   # gate di validazione
bash scripts/check_fleet_drift.sh                                 # git vs deploy
```
