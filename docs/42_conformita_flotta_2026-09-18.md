# 42 — Conformita' della flotta: la specifica misurata diventa un controllo (round 39)

## 42.1 Perche'

Il mandato e' "deploy solo di edge misurato e robusto". Con due sessioni che
scrivono sullo stesso repo (visto il 2026-09-17 e 18), un parametro ritoccato, un
asset aggiunto o un capitale disallineato non devono passare inosservati: la
strategia deployata deve essere ESATTAMENTE quella misurata.

## 42.2 Cosa controlla

`tools/trend_conformita.py` confronta i tre config di produzione con la
specifica deployata:

- **universo per macchina**: mc2 7 (BTC ETH SOL XRP DOGE TRX CRV), nuvola 6
  (LINK AVAX DOT UNI SUI MINA), MARCODG1 4 (ADA ARB XLM ALGO);
- **capitale del conto**: 42.12 / 24.83 / 42.04, con tolleranza 2% (i saldi si
  muovono col mercato);
- **9 parametri per bot**: canale 40, atr_period 14, trail_mult 2.5,
  stop_atr_mult 2.0, trend_ema 100, risk_pct 0.02, max_exposure 1.0, fee 0.0035,
  timeframe 1d;
- **modalita'**: `okx` (live), non paper;
- **mandato**: in live solo strategie con alpha misurato
  (`denaro/research/misurate.py`).

Esce 0 se conforme, 1 con l'elenco dei fallimenti: e' utilizzabile in un cron.

## 42.3 Esito sul deploy attuale

    12 controlli, 187 asserzioni sui parametri, 0 fallimenti
    la flotta deployata corrisponde alla specifica misurata

Un bug mio trovato e corretto mentre lo scrivevo: la chiave `timeframe` non e'
presente nei config (il Node usa il default `1d`), e il controllo la segnalava
come mancante in tutti e 17 i bot. Ora usa il default, che e' appunto cio' che fa
la produzione.

## 42.4 Quando usarlo

Prima di credere a un numero, dopo un riavvio, dopo un commit di un'altra
sessione, o come primo comando quando "qualcosa non torna":

    python3 tools/trend_conformita.py
