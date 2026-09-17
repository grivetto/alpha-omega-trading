# 28 — Il live non stava correndo la strategia misurata (round 28, 2026-09-17)

## 28.1 Il difetto, trovato prima che costasse

Le candele giornaliere di OKX EEA **non chiudono a mezzanotte UTC**: chiudono
alle **16:00 UTC** (mezzanotte UTC+8). Verificato su `eea.okx.com` il
2026-09-17: per UNI-EUR e BTC-EUR ogni `ts` delle barre `1D` ha
`ts % 86400 == 57600`.

Tutti i CSV su cui e' stata misurata la strategia
(`backtest_data/dl_*_1D.csv`) hanno **quello** stesso confine. Tutta la misura
— canale 40, trailing 2.5, universo a 17 asset, potatura di LTC/AAVE/ATOM — vale
per barre che chiudono alle 16:00 UTC.

La policy in produzione, invece, costruiva le barre dai tick con

    indice = int(now // 86400)

cioe' su una griglia a **mezzanotte UTC**, e `precarica_barre` scartava la
"barra di oggi" con lo stesso confine. Effetto: il canale (massimo a 40 barre) e
la chiusura su cui si decide il breakout erano **sfasati rispetto al backtest**.
Il live non stava correndo la strategia misurata: stava correndone una simile,
mai validata.

## 28.2 Perche' i test non l'avevano visto

Il backtest e la policy erano coerenti **tra loro** (le stesse barre iniettate),
quindi ogni confronto interno passava. Il difetto stava nel **confine**, che
nessun test confrontava con quello dell'exchange. E' la stessa classe di errore
dei minimi d'ordine del round 10: giusto nel modello, sbagliato nel mondo.

`tools/trend_monitor.py` escludeva correttamente la barra in corso, ma quello
copriva il fetcher usato dal monitor, non la griglia dei tick della produzione.

## 28.3 La correzione

- `TrendParams.offset_barre_s` (default `0` = mezzanotte UTC: retro-compatibile
  e corretto per exchange allineati a UTC).
- `precarica_barre` **ricava** il confine dalla griglia ricevuta: prende la fase
  dominante (`ts % periodo`, adottata se copre >= 75% delle barre) e la usa. Se
  le candele sono gia' a mezzanotte UTC l'offset resta 0, quindi per gli altri
  exchange non cambia nulla.
- `_aggiorna` chiude le barre su `int((now - offset) // periodo)` e scrive il
  `ts` della barra con lo stesso offset.
- `tools/trend_allineamento.py`: verifica in produzione, per ogni bot, confine
  ricavato, numero di barre, ultima barra chiusa e **prossima chiusura**.

## 28.4 Verifica

- 5 test nuovi in `denaro/tests/test_trend_allineamento.py`: offset ricavato
  dalle candele OKX, chiusura alle 16:00 UTC (non a mezzanotte), **canale
  identico a quello del backtest** dopo la chiusura della barra, griglia UTC
  invariata, offset esplicito accettato. Suite: **314 test verdi**.
- Live (2026-09-17 22:54 UTC, dopo il riavvio dei nodi): tutti e **17 i bot**
  con `offset = 57600`, 299 barre precaricate, ultima barra chiusa
  `09-16 16:00`, prossima chiusura **`09-18 16:00 UTC`** — cioe' la stessa
  griglia delle candele di ricerca.
- Deploy: commit `f9b51d8` su mc2, nuvola e MARCODG1; unit
  `denaro-node-*` riavviate e attive.

## 28.5 Cosa resta, dichiarato

- La barra costruita dai tick ha un OHLC **parziale** nel periodo in cui il nodo
  riparte: il massimo/minimo coprono solo dal riavvio al confine (es. dalle
  22:53 invece che dalle 16:00). La **chiusura** — l'unica cosa che decide il
  breakout — e' corretta al tick; l'ATR del periodo e i canali futuri risultano
  leggermente sottostimati (ordine di 0.1-0.2% di prezzo per una barra
  parziale). Prossimo passo: far iniettare al Node la **candela chiusa** al
  momento del confine, invece di ricostruirla dai tick.
- Nessun ordine e' ancora stato eseguito: la prima valutazione con la griglia
  corretta e' la chiusura delle **16:00 UTC del 2026-09-18** (18:00 CEST).
  Il candidato piu' vicino e' **UNI**, il cui prezzo attuale e' sopra il canale
  a 40 barre: se chiude sopra 6.4440 EUR, entra.

## 28.6 Dashboard: vedere la posizione

Round 28 ha anche chiuso il buco di telemetria aperto dal round 27: la card di
ogni bot in `denaro/dashboard_infra.html` ora mostra un badge **IN POS** e la
riga `IN POSIZIONE · ENTRY ... · STOP ...` (oppure `FLAT`), dagli stessi campi
`in_posizione`/`pos_entry`/`pos_stop` che il nodo scrive nel file health e
che il pusher Zabbix gia' pubblica. Commit `0e7cf41`.
