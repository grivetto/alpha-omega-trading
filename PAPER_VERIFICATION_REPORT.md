# PAPER TRADE VERIFICATION REPORT — 2026-08-05 (SESSIONE FINALE)

Obiettivo: verificare in paper TUTTI i tipi di trading progettati.
Stato: 115 USDT chiuso (banca in carico) — FUORI SCOPO. NESSUN DRY_RUN=0 eseguito.
Tutte le run: locale su MC2, zero chiavi private, zero ordini reali.

## TIPI DI TRADING E VERDETTO

### 1. GRID DENARO v5 (main.py + denaro_core.py + kraken_engine.py)
STATO: VERIFICATO END-TO-END (MOCK), restart-safe.
- Run MOCK_MODE=1 SHADOW_MODE=0 (stato pulito): 5 GRID BUY piazzati, 0 errori,
  equity stabile 100.00, shutdown graceful, libro ordini salvato.
- RESTART TEST (decisione storico): stato con 1 livello in stage=sell + sell_order_id
  iniettato -> dopo restart il libro ORDINI SOPRAVVIVE (stage=sell, sell id preservato).
  Il finding storico "state.py load() perde posizioni" riguardava il modulo rimosso
  PortfolioState (run_paper.py, non piu' nel repo) — NON si applica a CoreState v5.
- Limite: la riconciliazione attiva su ordini iniettati non e' esercitata (solo persistenza).
- Fill reali in MOCK avvengono (run precedente: EUR 80 / base 324 con fill).

### 2. DCA v5 (denaro_core.py:753-823)
STATO: VERIFICATO + 2 FIX APPLICATI (non committati).
- Harness 10 check: entry nuova, no-signal, open_position, drop entry, max_entries,
  exit target, trailing ratchet, trailing exit, stop loss, close PnL+reset — ALL PASS.
- FIX 1 (dead code): ramo trailing stop irraggiungibile — il ratchet era DOPO il check,
  quindi trail>0 sempre quando current>activation. Corretto in ratchet-then-trail
  (denaro_core.py:787-796). Ora l'exit trailing -1.5% dal picco funziona.
- FIX 2: dca_close_position() non resettava trailing_activation — dopo la chiusura la
  nuova posizione usciva subito in "trailing". Aggiunto reset (denaro_core.py:819).

### 3. SHADOWGRID (shadowgrid.py, md5 548a4fae)
STATO: LOGICA + PERSISTENZA VERIFICATE. NON DEPLOYATO.
- Harness A (round-trip buy->sell + fee): PASS, PnL +0.7481.
- Harness B (gap-down 3 livelli): PASS, cash mai negativo.
- Harness C (gap-down 5x25% sovra-levata): PASS, guardia cassa al fill (5° skip "no cash").
- PERSISTENZA: save -> reload -> secondo round-trip POST-restart: PASS (libro restaurato
  continua a tradare). Gap "sell path mai esercitato" CHIUSO.
- Run live locale (ticker ccxt pubblico, zero chiavi): 5 ordini buy, equity 100, 0 errori.

### 4. SCALPER v2 (scalper_v2.py) — RISCRITTO DA ZERO
STATO: CODICE NUOVO + HARNESS A/B/C/D ALL PASS + SMOKE LIVE OK. NON DEPLOYATO.
- Entry mean-reversion: prezzo scende >= ENTRY_DROP% dal massimo recente (ratchet).
- Exit: TARGET_PCT% (take-profit) OPPURE STOP_PCT% (stop-loss), fee incluse.
- Guardia cassa al fill: cost = entry+fee, mai comprare se cash insufficiente.
- Persistenza restart-safe: posizione + ratchet trade_high salvati e riletti.
- Scenario A (entry->target): PASS, PnL +0.3034, fee incluse.
- Scenario B (entry->stop):   PASS, perdita -0.6034 limitata allo stop.
- Scenario C (guardia cassa): PASS, ENTRY skipped quando cost > cash.
- Scenario D (persistenza):   PASS, posizione + ratchet ripristinati, continua a tradare.
- Smoke live locale (ticker ccxt DOGE/EUR, zero chiavi): cicli + health OK.
- Il vecchio scalper.py (archive/denaro_war/) era codice morto retired — non riusato.

### 5. STRATEGIE v6 (neo/) — harness offline, zero rete
STATO: VERIFICATE (logica).
- GridStrategy (passiva, nessun segnale): PASS.
- DCAStrategy (bear dump -> buy): PASS.
- ScalpStrategy (spread stretto -> buy): PASS.
- StrategySelector (cooldown/dca/scalp/grid per regime ATR/momentum): PASS.
- StateStore SQLite WAL: fix executemany verificato (DML su trades + state, journal WAL).
- FIX APPLICATO: neo/exchange.py Accept-Encoding "gzip, deflate" — risolve l'errore
  cronico "Can not decode content-encoding: br" (Kraken rispondeva br non decodificabile).
  Verificato live: ticker DOGE/EUR letto OK (last 0.0607), prima falliva al 100%.
- E2E: python -m neo.main (da root repo) -> cicli con prezzo reale, selector attivo
  (scalp per ATR basso), health server su unix socket risponde.
- VINCOLO DI AVVIO (bug noto): "python neo/main.py" (path assoluto) CRASHA per shadowing
  di types stdlib (ImportError GenericAlias). Deve partire con "python -m neo.main" dalla
  root o systemd con WorkingDirectory + -m.
- GAP (design): v6 genera segnali ma NON piazza ordini (observation mode) — il fill
  engine e' assente per design. Non e' verificabile un round-trip v6.

## FIX APPLICATI — COMMITTATI E PUSHATI su fix/paper-verification (NON su origin/main)
Branch: fix/paper-verification → origin (verificato via ls-remote).
- 2729327b: denaro_core.py trailing stop DCA raggiungibile + reset trailing_activation
  in close; neo/exchange.py Accept-Encoding gzip/deflate (fix brotli); neo/state.py
  executemany; harness v6/sell_path/persistenza/dca + report. Harness TUTTI PASS.
- 9fb65b05: shadowgrid.py (548a4fae) + shadowgrid-*.service corrette (senza
  StandardOutput=append — era la causa del crash-loop 7577/7683 restart sui nodi).
- 1a9031f4: scalper_v2.py + harness_scalper_v2.py (A/B/C/D ALL PASS) + report.
- backup/prequel-main = copia dei commit della vecchia lineage (d26f8976), NON cancellare.

## STATO DEPLOY FINALE — TUTTO OPERATIVO IN PAPER (2026-08-05 22:45)
Nessun ordine reale: MOCK_MODE=1 / SHADOW_MODE=0 / ticker ccxt pubblico. Zero chiavi usate.

| Servizio | Nodo | Stato | Health |
|----------|------|-------|--------|
| kraken_bot.service (Grid v5 DOGE/EUR MOCK) | MC2 | ACTIVE (fix: puntava a kraken_bot/main.py inesistente -> 16.919 crash-loop; ora main.py MOCK_MODE=1) | log journal OK |
| scalper_v2.service (DOGE/EUR mean-rev PAPER) | MC2 | ACTIVE (nuovo) | :8913 OK |
| shadowgrid-kraken.service (SOL/EUR PAPER) | nuvola | ACTIVE, 0 restart, binario 548a4fae | :8912 OK |
| shadowgrid-mexc.service (SOL/USDT PAPER) | MARCODG1 | ACTIVE, 0 restart, binario 548a4fae | :8911 OK |

- Causa crash-loop originale (7577/7683 restart): log root-owned + StandardOutput=append.
  Unit corrette senza quella riga; log root-owned rimossi su entrambi i nodi.
- chown nuvola completato (binario sergio:sergio).
- Scalper v2: deployato come servizio su MC2 (:8913).

## ARTEFATTI OBSOLETI / DA RIMUOVERE
- state_load_fix.patch: STALE — targetta core/state.py (modulo PortfolioState rimosso).
  DA ELIMINARE (mai applicare: git apply da "corrupt patch at line 64").
- PAPER_VERIFICATION_REPORT.md precedente: superato da questo documento.
- SMOKE_TEST_EVIDENCE.md: storico, superato da harness_sg_persistence.py.

## ALBERO GIT (modifiche pre-esistenti di altra sessione, NON mie)
main.py (RECOVERY_MODE v6), mexc_engine.py, bybit_engine.py, neo/core.py (pair helpers),
neo/main.py, neo/state.py (executemany) — diff della sessione handoff v6, salvati in
stash@{0} (wip-altra-sessione-v6). Da non attribuire a questa verifica.

## RISPOSTA ONESTA A "FUNZIONA ALLA PERFEZIONE?"
- Grid v5: code-verified + restart-safe + fill MOCK osservati. LIVE-FILL su mercato
  reale dipende dal movimento dei prezzi (i livelli buy stanno sotto il mid).
- DCA v5: verificato, 2 bug reali trovati e fixati (committati).
- ShadowGrid: round-trip completo + persistenza verificati; DEPLOYATO in PAPER
  su nuvola (SOL/EUR :8912) e MARCODG1 (SOL/USDT :8911), 0 restart.
- Strategie v6: logica verificata, fill engine assente per design.
- Scalper v2: riscritto da zero, harness A/B/C/D ALL PASS, smoke live OK,
  DEPLOYATO in PAPER su MC2 (:8913).
- Tutti i servizi girano in PAPER (MOCK_MODE=1, zero chiavi). LIVE richiede GO esplicito.

Nessun DRY_RUN=0 eseguito. 115 USDT chiuso (banca in carico). Tutto il deploy è PAPER.
