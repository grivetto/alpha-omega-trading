# Audit 5 Pilastri — Alpha-Omega / Denaro (DeepSeek Brain)

Data: 2026-08-27 · Scope: Node Denaro (3 macchine: MARCODG1, nuvola, mc2),
capitale reale spot ~105€ (OKX main + 2 sub-account + Kraken) · Ambiente: spot
only (nessun rischio liquidazione margin/futures: **il rischio è di
prezzo/capitale, non di liquidazione**).

---

## Stato attuale per pilastro

| Pilastro | Già presente | Carenze critiche |
|---|---|---|
| 1 Alpha | Grid bilaterale (sell ladder), AdaptiveEngine (ADX/ATR/EMA200), RegimeFilter, Momentum/MeanRev | Nessun Hurst/VWAP/order-flow; DCA su ATR solo parziale; volume non usato |
| 2 Risk | CB vol-scaled, drawdown, Kelly con VaR cap, stop-loss per bot, preflight anti-deadlock, daily loss | **Niente stop settimanale**, **nessun vol-target esplicito**, **nessuna tolleranza slippage**, exposure condivisa su conto OKX main non gestita |
| 3 Architettura | asyncio, WS auto-reconnect + fallback REST (hub), journal fsync+replay, SQLite WAL, stato JSON | Niente priority queue cancel/stop; rate-limit solo ccxt; **sessioni ccxt.pro non chiuse** ("Unclosed client session"); journal append-only senza rotation |
| 4 Backtest | Backtest grid 1h (brain/strategy_lab.py) | **Look-ahead bias (fill valutato su close)**, slippage fisso, **niente WFA né Monte Carlo**, fee maker/taker non distinte |
| 5 Telemetria | Health JSON con pnl/drawdown/regime, Zabbix, dashboard, Brain (push + auto-heal), ponte Hermes | **Mancano Sharpe/Sortino/Calmar/Profit Factor**, **latency tick-to-trade non misurata**, alert solo Telegram |

---

## Falle logiche trovate (concrete, verificate sul codice)

### F1 — Schema Pydantic scartava `sell_*` → griglia bilaterale MAI attiva
`denaro/application/config.py` (BotConfigSchema) non dichiarava
`sell_levels/sell_distance/sell_step/sell_asset_share/level_step/retarget_factor`
→ Pydantic (`extra="ignore"` di default) li scartava in silenzio →
`build_grid_params` riceveva `sell_levels=0` → i bot compravano sotto ma **non
vendevano mai l'asset sopra**. Verificato a runtime su MARCODG1 (tutti `None`).
**FIXATO**: campi aggiunti allo schema + test (`denaro/tests/test_overrides.py`).
Journal dopo il fix: `grid bilaterale SOL/EUR: 2 sell ladder piazzati` ecc. su
tutte le macchine. Lezione: **qualsiasi campo nuovo va aggiunto allo schema**;
il dump `to_dict()` non è un pass-through.

### F2 — Conto condiviso OKX main: 3 bot, 1 equity, CB condiviso
SOL/DOGE/ETH condividono l'account OKX main (~28€). Ogni bot ha il proprio
`RiskManager`/`CoreState`: il drawdown del conto è comune ma misurato 3 volte
su basi diverse (`capital` 15/3/9) → lo stop-loss di un bot scatta in ritardo
rispetto all'equity reale. Mitigazione attuale: stop 0.15 e daily 0.05 per bot.
**Fix proposto**: equity reale condivisa passata a tutti i bot dello stesso
account (già `get_equity=exchange.fetch_total_equity` → è la stessa; ma i
`CoreState` partono da capital diversi) → allineare i `day_start_capital` dei
bot dello stesso account alla equity condivisa al boot.

### F3 — Preflight con capitale non allineato → blocco persistente
`per_level = capital/levels` vs `free reale`: con EUR 0.83 e per_level 1.0 il
buy è bloccato (corretto) ma il bot resta "in errore" per ore finché il sell
ladder non genera EUR. **Fix**: vol-targeting (F7) + ricalcolo per_level su
`free+locked×0.85` (già in `PortfolioManager.total_available`, da usare in
`per_level`).

### F4 — Look-ahead bias nel backtest (P4)
`brain/strategy_lab.py:backtest_grid` valuta il fill dei limit order sulla
`close` della barra. Se la barra tocca il prezzo del limit e chiude oltre,
il fill è già decisione ex-post. **Fix**: fill buy se `low <= price`, fill
sell se `high >= price` (niente `close`).

### F5 — Journal append-only senza rotation (memory/disk leak)
`_trades.jsonl` cresce senza limite (23KB in 2 giorni su un paper). A 30 tick/min
× 5 bot × 1 anno → GB. **Fix**: rotation giornaliera + keep 30 giorni (o
truncate su soglia).

### F6 — Sessioni ccxt.pro non chiuse (memory leak)
Nei journal dei nodi: `[ERROR] asyncio: Unclosed client session` a ogni
restart. **Fix**: `await ex_pro.close()` nel teardown del hub
(`denaro/infrastructure/market_data.py`), try/finally in `NodeApp.run`.

### F7 — Sizing fisso, non risk-scaled (P2)
`per_level = capital/levels` fisso: in regime `extreme` la griglia continua a
espandere il rischio mentre `sizing_multiplier` (che esiste in RiskManager!)
non viene applicato al per_level. **Fix**: `per_level = capital/levels ×
min(1, kelly_fraction × vol_adj)` + vol-target `σ_target/σ_asset`.

### F8 — Nessuna tolleranza slippage (P2)
Gli stop-loss e i sell usano ordini market (`sell_market`); nessun check su
spread/deriva tra prezzo atteso e fill. **Fix**: prima di un market order,
se `|last - mid|/mid > max_slippage` (default 0.5%) → blocca + alert.

### F9 — Nessuno stop settimanale (P2)
Esiste solo `daily_loss_limit`. Una settimana con perdite giornaliere sotto
soglia (4×2% = -8%) non ferma nulla. **Fix**: `weekly_loss_limit` (default
0.20) con reset a inizio settimana (lunedì 00:00 UTC).

### F10 — Metriche telemetria incomplete (P5)
Health ha pnl/drawdown ma non Sharpe/Sortino/Calmar/ProfitFactor/latenza.
**Fix**: calcolo nel BotTask a ogni tick (window 50 trade) + push Zabbix +
dashboard.

---

## Fondamento matematico delle ottimizzazioni

### Kelly frazionario (P2)
Per una scommessa con probabilità di vincita `p`, payoff odds `b = avg_win/avg_loss`:
`f* = (b·p − (1−p)) / b`. Kelly massimizza il logaritmo della ricchezza ma è
aggressivo → si usa **frazione k=0.25** (half-quarter Kelly) e cap `f*·k ≤ 0.50`.
Nel nostro caso: `b = profit_target / (buy_distance + 2·fee)` per il singolo
ciclo grid; `p` = win-rate rolling (50 trade). Già implementato in
`RiskManager.calculate_kelly` — **manca l'applicazione al per_level** (F7).

### Volatility Targeting (P2)
Dimensione posizione inversamente proporzionale alla volatilità realizzata:
`N_t = C · σ_target / σ_t` con `σ_t = ATR% (14) · √(1h annualizzata)` oppure
dev std dei rendimenti su finestra 20. Scala automaticamente la griglia nei
regimi caldi (σ alto → meno capitale per livello). Interazione con il regime
ADX/ATR già calcolato dal RegimeFilter.

### Hurst exponent (P1)
`H` da R/S analysis su finestra rolling (es. 200 barre 1h):
- `H > 0.55` → persistenza (trend) → favorire trailing/momentum, grid largo;
- `H < 0.45` → anti-persistenza (mean-reverting) → grid tight, più livelli;
- `0.45 ≤ H ≤ 0.55` → random walk → grid neutro.
`E[R/S]_n = c·n^H`; stimo `H` da regressione log-log su sub-finestre.
Complementare ad ADX (che è lagging): Hurst misura la struttura, ADX la forza
del trend corrente. Riferimento: [nautilus_trader Hurst/VPIN](https://github.com/nautechsystems/nautilus_trader/blob/3eb18933/docs/tutorials/hurst_vpin_kraken.md?plain=1#1).

### Walk-Forward Analysis (P4)
Anti-overfitting: finestre scorrevoli `[train | test]` (es. 200|100 barre 1h).
Si ottimizza SOLO su train, si valuta SOLO su test; il parametro vincente è
quello che generalizza (media delle performance test, non il best assoluto).
Si evita l'overfitting del grid di parametri sul periodo unico. Riferimento:
[FT-QFLRSIPNR-HOPT (walk-forward per freqtrade)](https://github.com/marianolatorre/FT-QFLRSIPNR-HOPT#1).

### Monte Carlo (P4)
Bootstrap dei trade realizzati (resample con replacement, 10k iterazioni) →
distribuzione del PnL finale; il **5° percentile** è il drawdown "in coda" da
usare per il sizing (VaR storico). Complementa il Kelly: Kelly dimensiona
l'edge, MC dimensiona il rischio di coda.

### Slippage & fee realistiche (P4)
- fee maker/taker separate: grid limit = maker (es. OKX spot 0.1% o 0.08%),
  stop market = taker;
- slippage dinamico: `slip = k · √(notional / volume_medio)` (modello di
  impatto quadrato) con floor 0.02% e cap 0.5%;
- fill: buy se `low ≤ price` (parziale: `fill_frac = 0.5 + 0.5·(price−low)/(high−low)`
  cap 1.0), sell speculare su `high`.

### Sortino/Calmar (P5)
`Sortino = (R̄ − rf) / σ_downside` (dev std dei rendimenti negativi);
`Calmar = CAGR / MDD`; `ProfitFactor = gross_win / gross_loss`;
`Sharpe = (R̄ − rf) / σ` annualizzato (√(24·365) su 1h). Latenza
`tick-to-trade = t_conferma − t_tick` misurata nel `BotTask.tick`.

---

## Piano di implementazione (priorità)

1. **P2 Risk** (in corso): weekly stop, vol-target per_level, slippage tolerance,
   allineamento equity condivisa OKX main.
2. **P4 Backtest**: fill high/low, WFA, Monte Carlo, fee maker/taker, slippage
   dinamico — in `brain/strategy_lab.py` (il ranking diventa WFA-based).
3. **P1 Alpha**: Hurst + volume/VWAP nel RegimeFilter; DCA su ATR% (già
   parziale in AdaptiveEngine) esteso al grid.
4. **P5 Telemetria**: metriche Sharpe/Sortino/Calmar/PF + latenza in health,
   push Zabbix, alert webhook/Telegram via Hermes.
5. **P3 Architettura**: priority queue cancel/stop con token bucket,
   `ex_pro.close()` nel teardown, rotation journal, recovery SQLite verificata.

## Riferimenti
- Hummingbot (grid/MM/WS): https://github.com/hummingbot/hummingbot
- Freqtrade (hyperopt/WFA): https://github.com/freqtrade/freqtrade
- CCXT/CCXT Pro: https://github.com/ccxt/ccxt
- Nautilus Trader Hurst/VPIN: https://github.com/nautechsystems/nautilus_trader
- Quantpedia: https://quantpedia.com
- VectorBT: https://vectorbt.dev
- Tardis.dev (microstruttura): https://tardis.dev
