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

## 29.5 Pre-flight del primo ingresso (23:03 UTC)

`tools/trend_preflight.py` costruisce la STESSA policy del Node, forza il confine
di barra e chiede alla policy cosa farebbe, senza piazzare nulla. Al prossimo
confine (09-18 16:00 UTC):

| asset | prezzo ora | canale | sopra | entry | amount | nozionale | stop | rischio |
|---|---|---|---|---|---|---|---|---|
| UNI | 6.6410 | 6.4440 | **SI** | 6.6443 | 0.4945 | 3.29 EUR | 5.6502 | 0.492 EUR (1.98%) |
| LINK | 9.9000 | 11.7870 | - | 11.9108 | 0.3706 | 4.41 EUR | 10.5842 | 0.492 EUR |
| AVAX | 6.6170 | 7.1120 | - | 7.1867 | 0.7633 | 5.49 EUR | 6.5426 | 0.492 EUR |
| DOT | 0.9400 | 1.1052 | - | 1.1168 | 3.5595 | 3.98 EUR | 0.9787 | 0.492 EUR |
| SUI | 0.6417 | 0.8156 | - | 0.8242 | 4.8588 | 4.00 EUR | 0.7230 | 0.492 EUR |
| MINA | 0.0854 | 0.0982 | - | 0.0992 | 31.095 | 3.08 EUR | 0.0834 | 0.492 EUR |
| BTC | 66594 | 70760 | - | 71504 | 0.000199 | 14.21 EUR | 67307 | 0.834 EUR (1.98%) |
| TRX | 0.2914 | 0.3000 | - | 0.3032 | 87.683 | 26.58 EUR | 0.2937 | 0.834 EUR |

Tutti e **17** gli asset passano il controllo del **minimo reale
dell'exchange** (il piu' stretto: BTC 0.0001 = 6.67 EUR, coperto da 14.21 EUR) e
il sizing esce a **1.98% del capitale** di rischio, cioe' il 2% previsto meno il
buffer fee. Il rischio e' quello misurato: nessun parametro e' stato ritoccato
per far entrare il primo ordine.

Nota di capacita': su mc2 il nozionale di TRX (26.58 EUR su 42.12) e di BTC
(14.21 EUR) dice che **due** posizioni a bassa volatilita' riempiono il conto.
E' esattamente il vincolo che il simulatore a capitale condiviso misura; se piu'
segnali scattano insieme, i successivi vengono ridotti dalla cassa libera.
