fix(telemetria+C7): equity inattendibile non si sostituisce; la dashboard distingue live da paper e marca lo stale

Due difetti osservati dal vivo il 2026-09-16.

C7 — equity sostituita con un valore inventato
BotTask._guard_equity, su lettura fuori range, restituiva l'ultimo valore
valido o — in mancanza — cfg.capital. Su mc2 questo produceva migliaia di
volte al giorno:
    [WARNING] equity sospetta 0.0852 per SOL/EUR -> uso 12.0000
    [INFO]    TICK SOL/EUR: price=85.85 free=0.0005 equity=12.0000
con 0.0005 EUR liberi reali. Drawdown, circuit breaker e stop-loss venivano
calcolati su un numero stabile e falso: il rischio reale spariva dalla
metrica. Ora _guard_equity restituisce None e il tick viene saltato — nessun
ordine, nessuna baseline aggiornata. In health si scrive il valore GREZZO
letto, non un sostituto.
La stessa modifica e' replicata in backtest/runner.py: se il backtest
continuasse a sostituire l'equity, misurerebbe una strategia diversa da
quella live.

Telemetria — la dashboard dichiarava +26,44 EUR di PnL contro -0,30 reali
- node_total_pnl sommava il PnL dei bot PAPER (equity virtuali da 100-300
  EUR) a quello reale. Ora conta solo i bot live; il paper ha la sua voce
  node_paper_pnl.
- I bot con health vecchio contavano come "running": nodi spenti da giorni
  (trend_sol_kraken.json fermo al 24 agosto, nuvola da 23 ore) apparivano
  attivi. Ora ogni bot porta age_s e stale, e i totali ignorano gli stale.
- Nuove voci per la dashboard: node_live_bots, node_paper_bots,
  node_stale_bots.

Test: 3 regressioni per C7 (equity fuori range basso/alto/NaN -> None; equity
plausibile -> restituita). Suite: 243 passed.
