# 55 — Requisiti per un esecutore "provato": cosa deve dimostrare, e cosa abbiamo già

Data: 2026-09-23. Su richiesta del proprietario: *"cercami fee più basse, lo short, e un
esecutore provato"*. Questo documento copre la terza voce. Non dice **quale** motore scegliere
(quello è oggetto della ricerca in corso sulle alternative): dice **cosa deve saper fare** e
**come si verifica**, così la scelta si fa su prove e non su impressioni.

Serve in entrambi gli scenari: se adottiamo un framework, è la lista di controllo; se
correggiamo il motore in casa, è il criterio di accettazione.

---

## 55.1 Cosa esiste già in casa (da NON riscrivere)

L'audit aveva ragione su un punto e torto su un altro: manca il **cablaggio**, non i
mattoni. Inventario verificato:

| primitiva | dove | stato |
|---|---|---|
| Misura anti-truffa da curva equity (Sharpe, Sortino, Calmar, maxDD, `warm`) | `domain/equity.py:37` (`EquityTracker`) | **esiste ed è usata solo dai test**: il percorso live pubblica i PnL per-trade, che `equity.py:5-8` dichiara inaffidabili |
| ATR di Wilder, unica implementazione condivisa ricerca/produzione | `domain/indicators.py:302` (`atr_wilder`) | usata da `research/eval.py` e `domain/trend.py` |
| Riserva fee/slippage sul sizing | `domain/sizing.py:20` (`FEE_BUFFER = 1%`) | in uso |
| Cap di esposizione **per bot** | `domain/trend.py:60,493`; letto da `denaro_node.py:176` | in uso, **default 1.0 = spento**, e non è mai impostato nei config |
| Cap di esposizione per **regime** (griglia) | `domain/risk.py:68` (`exposure_limit`), `:280` (`exposure_factor`) | in uso nella griglia |
| Circuit breaker, stop-loss di bot, guardia equity (C7), safemode RAM/CPU | `application/orchestrator.py`, `safemode.py`, `supervisor.py` | in uso |
| Cancello OOS a 6 prove | `research/eval.py:1143-1155` | in uso |
| Verifica del trade eseguito contro il modello | `tools/verifica_trade*.py`, commit `5489d68` | in uso |

**Conseguenza operativa**: la voce "misura onesta" dell'obiettivo non richiede un modulo nuovo,
richiede di collegare `EquityTracker` al percorso live e di persistere la curva. Chi propone di
scrivere un ledger nuovo sta proponendo di duplicare ciò che esiste già.

## 55.2 I requisiti — sei prove, non sei opinioni

Un esecutore è "provato" quando queste sei cose sono dimostrabili. Ognuna deriva da un difetto
misurato o da un bisogno misurato della strategia.

### Q1 — L'uscita è dimensionata sulla POSIZIONE, non sul saldo
- **Perché**: R1. `orchestrator.py:879-891` vende il saldo libero dell'asset; con più bot su un
  conto (o asset detenuti a mano) liquida tutto il conto. Difetto **in due punti** di vendita.
- **Verifica**: test `test_R1_*` in `denaro/tests/test_rischi_capitale.py`. Con 1,0 di saldo e
  una posizione di 0,25, deve vendere 0,25.

### Q2 — Uno stop che fallisce viene RITENTATO, e lo stato non è aggirabile dall'esterno
- **Perché**: R2. Oggi il flag resta `True` e il tick non ritenta mai (`:361-364` vs
  `:1033-1038`); e il blocco dei nuovi ordini vive in `trading_paused` (`:134`, `:498`), che non
  è persistito e viene riscritto da `denaro_node.py:478`.
- **Verifica**: test `test_R2_*`. Il secondo tick deve ritentare; con `stop_loss_triggered`
  persistito, azzerare il flag in memoria non deve riabilitare gli ordini.

### Q3 — Gli ordini hanno una chiave di idempotenza, e l'id è durevole prima del ritorno
- **Perché**: R3. Zero `clientOrderId` in `denaro/`; i buy partono a `:605-618` e lo stato si
  persiste a `:623`: un crash in mezzo lascia ordini vivi non tracciati.
- **Verifica**: `create_limit_order` accetta una chiave deterministica (es. `bot_key:level:side`)
  e l'ordine è recuperabile dopo un riavvio simulato.

### Q4 — I fill parziali sono contabilizzati
- **Perché**: `filled` non è letto da nessuna parte in `application/`. Un ordine riempito in
  parte e poi cancellato esce dallo stato senza contabilizzare il riempito
  (`orchestrator.py:1131-1132` per i buy, `:1170-1171` per le sell); e un fill chiuso registra
  `info["amount"]` — il **richiesto** — invece di quanto la sede ha davvero riempito
  (`:1079`, `:1139`). Effetto: il saldo all'exchange e lo stato del bot divergono, in silenzio.
- **Verifica**: tre test in `denaro/tests/test_rischi_capitale.py`, verificati in esecuzione:
  - `test_Q4_buy_parzialmente_eseguito_non_sparisce_dallo_stato` → l'ordine con 0.4 su 1.0
    viene rimosso: `open_buys={}`, `posizione_aperta=None`. Il 0.4 esiste sul conto e da
    nessuna parte nello stato.
  - `test_Q4_sell_parzialmente_eseguita_contabilizza_il_riempito` → 0.4 venduti davvero e
    `total_trades = 0`: il ricavo e la fee di quella vendita non esistono.
  - `test_Q4_un_fill_chiuso_usa_la_quantita_riempita_non_quella_richiesta` → posizione
    registrata **1.0** dove la sede ha riempito **0.7**: posizione e PnL sovrastimati del 43%.

### Q5 — La performance si misura dalla CURVA EQUITY, persistita
- **Perché**: la misura per-trade si azzera a ogni riavvio, non registra gli stop-loss e mescola
  euro e percentuali (`domain/equity.py:5-8`).
- **Verifica**: dopo un riavvio, Sharpe e maxDD ricostruiti dalla curva persistita coincidono con
  quelli di prima del riavvio. `EquityTracker.warm` deve restare `False` finché la storia non
  basta: nessun numero parziale spacciato per significativo.

### Q6 — Esiste un limite di esposizione A LIVELLO DI CONTO
- **Perché**: oggi il cap è per bot (`trend.py:493`, default 1.0 = spento). Con 17 bot nessun
  componente guarda la somma. Il massimo teorico misurato è 258 € su 1.000 (26%, `docs/54` §54.3),
  ma è un risultato, non un vincolo.
- **Verifica**: con N posizioni aperte che superano il cap configurato, il bot successivo non
  apre. Il cap è sul **totale impegnato**, non sul numero di bot.

### Q7 — L'esecutore sa esprimere la strategia MISURATA, senza cambiarla
- **Perché**: l'edge è misurato con parametri fissi — trailing a **2,5 ATR**, stop iniziale a 2 ATR,
  breakout del canale a 40 barre, filtro EMA 100. Un esecutore che offre solo un trailing in
  **percentuale di PnL** non esprime quella strategia: ne esprime una diversa, e la misura non si
  trasferisce. Il progetto lo sa già: `atr_wilder` è **una sola** implementazione condivisa fra
  ricerca e produzione, perché *"averne due copie renderebbe l'equivalenza tra backtest e live una
  coincidenza, non una garanzia"* (`domain/indicators.py:304-309`).
- **Verifica**: la documentazione dell'esecutore mostra un trailing ancorato all'**ATR** (non a una
  percentuale), e la strategia portata produce gli **stessi segnali** del backtest sulle stesse
  barre.

## 55.3 La domanda che decide fra adottare e correggere

> Il framework risolve Q1-Q7, o li **sposta** soltanto?

Un motore maturo può benissimo avere un exit dimensionato sul saldo se l'adapter lo permette, o
non avere il cap di conto perché assume un bot per conto. Quindi la verifica non è "il framework
è famoso", è: **per ognuna delle sette voci, mostra il punto del codice o della documentazione che
la soddisfa.** Se per una voce la risposta è "va scritto", allora quella voce ha lo stesso costo
di scriverla in casa — e va contata nel confronto.

Criterio di decisione proposto: adottare un framework conviene se soddisfa **Q3, Q4 e Q6** senza
codice nuovo (sono le voci in cui un motore maturo ha davvero più esperienza del nostro), e se il
**dry-run è documentato come fedele** — perché il difetto di fondo di questo progetto non è la
strategia, è che il percorso di esecuzione non è mai stato provato con denaro vero.

## 55.4 Cosa manca oggi, in una riga per voce

| voce | stato |
|---|---|
| Q1 uscita sulla posizione | **manca** (due punti di vendita) |
| Q2 retry + stato non aggirabile | **manca** |
| Q3 idempotenza ordini | **manca** (zero occorrenze) |
| Q4 fill parziali | **manca** |
| Q5 misura da curva equity | **esiste, non collegata** |
| Q6 cap di esposizione di conto | **manca** (esiste solo per bot, spento) |
| Q7 fedeltà alla strategia misurata (trailing ATR) | **da verificare per ogni candidato**: un trailing in % di PnL cambia la strategia |
