# 29 — La barra dei tick sostituita dalla candela vera (round 29, 2026-09-17)

## 29.1 Il residuo del round 28

Il round 28 ha allineato il **confine** delle barre a quello dell'exchange (16:00
UTC), ma la barra del periodo in corso era ancora costruita **dai tick**: il suo
massimo/minimo coprono solo dal riavvio del processo al confine (es. dalle 22:53
invece che dalle 16:00). Quella barra entra poi nel canale a 40 barre per i
giorni successivi, quindi ogni riavvio abbassa un po' il canale live rispetto a
quello misurato e fa entrare la strategia piu' spesso di quanto sia stato
verificato. Con i riavvii di oggi (deploy, healer) non era teoria.

## 29.2 La correzione

- `TrendPolicy.aggiorna_storico(barre, now)`: **sostituisce** lo storico con le
  candele chiuse appena scaricate. `precarica_barre` aggiunge in coda all'avvio;
  questa rimpiazza, cosi' la barra dei tick viene cancellata e rimpiazzata dalla
  candela vera. Se il payload e' corto o illeggibile
  (< `max(canale, atr_period, trend_ema) + 5`) **ripristina** lo storico
  precedente: senza canale e ATR la policy non entra e non protegge, e restare
  ciechi e' peggio che tenere dati vecchi di un minuto.
- `TrendPolicy.on_ohlcv(symbol, ohlcv)`: contratto del canale OHLCV del Node.
- Il canale OHLCV esisteva gia' nell'orchestratore per la policy adattiva
  (1h, 200 barre, refresh 60s). Ora `add_ohlcv_source` accetta **timeframe e
  limit per simbolo** e il Node passa `1d` e 300 barre: le STESSE candele del
  precaricamento, altrimenti canale e ATR cambiano sotto i piedi al primo
  refresh.

Effetto: entro 60 secondi dalla chiusura, la barra provvisoria dei tick viene
sostituita dalla candela vera dell'exchange. Canale, EMA e ATR restano identici
a quelli del backtest. La decisione di ingresso resta al confine (chiusura =
ultimo tick, entro l'intervallo di poll) e il sizing usa l'ATR di quel momento.

## 29.3 Verifica

- 3 test nuovi in `denaro/tests/test_trend_allineamento.py` (suite: **317
  verdi**): la candela vera prende il posto della barra piatta dei tick; un
  payload corto o vuoto non azzera canale e ATR; entrambe le firme di
  `on_ohlcv`.
- Live: tutti e **17 i bot** con `ohlcv source ... avviato` nei log, zero fetch
  fallite, health freschi e senza errori su mc2 (7/7), nuvola (6/6), MARCODG1
  (4/4).
- Commit `0f9f8b5` su mc2, nuvola e MARCODG1; `denaro-node-*` riavviate.

## 29.4 Cosa resta

- La valutazione del breakout avviene al **confine** con la chiusura dell'ultimo
  tick (poll ~30s), non con la chiusura ufficiale della candela: la differenza e'
  il movimento di 30 secondi. Per usare la chiusura ufficiale servirebbe spostare
  il trigger del segnale sulla candela — e decidere prima cosa fare quando il
  nodo riparte a cavallo del confine (entrare in ritardo = inseguire).
- Prima valutazione con la catena completa e allineata: chiusura delle **16:00
  UTC del 2026-09-18** (18:00 CEST). Candidato piu' vicino: **UNI**, sopra il
  canale a 40 barre.
