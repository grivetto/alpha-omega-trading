# 35 — Health letti in una ssh per host, non una per bot (round 33-34)

## 35.1 Il difetto

L'aggregator legge i health dei bot live "extra" (17 bot su 3 host) con una
**ssh separata per bot**: 10 connessioni per ciclo solo per nuvola+MARCODG1. Se
una qualunque falliva, quel bot **spariva dalla dashboard per un ciclo intero**
(`status: no_file`). Osservato il 2026-09-17 su `nuvola:okx:AVAX/EUR`, che
compariva e spariva fra un ciclo e l'altro.

Non era un problema di dati: il health file era fresco (scritto ogni 30s con
scrittura atomica). Era il percorso di lettura.

## 35.2 La correzione

- **Una ssh per host**: i path dei bot di un host vengono letti con un solo
  comando (`for f in ...; do echo ===FILE===; cat "$f"; echo; done`), quindi il
  parsing e' raggruppato e testabile (`_parse_dump`, funzione pura).
- **Niente `[ -f ]`**: se un file manca, `cat` non stampa nulla e il blocco
  resta vuoto. Un test malformato (`[ -f "$f"]`, senza spazio) faceva uscire
  `ssh` con codice diverso da zero e faceva sparire **tutti** i bot di
  quell'host: e' esattamente l'errore commesso e corretto in questo round.
- **Ultima lettura buona per 300s**: un singolo timeout non spegne un bot che
  sta lavorando; un guasto vero (>300s) resta visibile come stale.

## 35.3 Verifica

- 4 test nuovi su `_parse_dump` (una riga, JSON multi-riga, dump vuoto/sporco,
  ordine preservato): suite **324 passed, 3 skipped** su MARCODG1.
- Live: tre cicli consecutivi dell'aggregator con **0 problemi su 17 bot**,
  eta' 22-24s, equity 109.58 EUR (prima: AVAX intermittente, poi — con il comando
  malformato — tutti e 6 i bot nuvola a `no_file`).
