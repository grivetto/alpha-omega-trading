# 63 — Carry Fase 2: pianificatore multi-coppia (spec di implementazione) — 03/10/2026

STATO: consegnata a **DSH-MC2** (canale `hermes_bridge/dsh-mc2/`, REQ F2, 03/10).
Il **pianificatore** è un modulo PURO (qui sotto). L'**esecuzione ordini** resta
riservata a Hermes sul percorso del denaro: questo componente non invia nulla.

## Contesto e riferimenti
- Fase 1 (canary C1, DOGE) è attiva; review formale **15/10** (docs/16).
- Fase 2 = carry multi-coppia sul conto OKX main. Piano scala: `money/docs/20`.
- Esecutore di riferimento (singola coppia, da estendere dopo): `carry/canary_carry.py`.
- Evidenza funding: P12 (payback per coppia: DOT 8g, DOGE 15g, LINK 15g, ADA 16g,
  XRP 19g, LTC 22g, AVAX 23g; baseline always-on; BTC/ETH esclusi).

## Obiettivo del modulo
Dati (specifiche strumenti, capitale disponibile, target di nozionale per coppia,
prezzi), produrre **piani deterministici e validati** per: apertura, chiusura,
riconciliazione e riepilogo di N coppie *spot-long + X-Perp-short 1× isolated*.

## Vincoli di sicurezza (non negoziabili)
1. Solo **stdlib**; nessun import `ccxt`/rete/socket; nessun I/O oltre input/ritorno.
2. Funzioni **pure** + dataclass `frozen`; determinismo (stessi input → stessi output).
3. Ogni violazione → `ValueError` con messaggio chiaro. Mai output non-finiti o negativi.
4. Il modulo **non decide** il capitale: riceve budget/nozionali; applica regole e rifiuta.

## Modello dati (adattabile se motivato)
- `InstrumentSpec`: base, ct_val, min_ct, ct_step, spot_min, spot_step
- `PairPlan`: base, contratti, spot_qty, nozionale_stimato, costo_spot, margine_stimato, delta_residuo
- `PortafoglioPlan`: piani, scartate[(base, motivo)], commit_totale, note

## Funzioni richieste (firme indicative)
1. `pianifica_coppia(spec, nozionale_target, prezzo_spot, prezzo_perp) -> PairPlan`
2. `pianifica_portafoglio(specs_ordinate, capitale_commit, nozionale_per_coppia, prezzi) -> PortafoglioPlan`
3. `calcola_delta(spot_qty, contratti, ct_val) -> float` e `entro_tolleranza(...)`
4. `riconcilia(stato_atteso, istantanea) -> list[Diff]` (spot, contratti; verdetto ok/ko)
5. `pianifica_chiusura(stato) -> list[AzioneChiusura]` (perp reduceOnly PRIMA, poi spot sell)
6. `riepilogo(piani_o_stato) -> dict` (totali spot/margine/delta/nozionale; per dashboard/alert)

## Regole numeriche (dichiarate, da rispettare nei test)
- Sizing: nozionale `N` per gamba; **capitale per coppia ≈ 2N** (spot + margine isolated 1×).
- Allineamento gambe: contratti quantizzati a `ct_step` (min `min_ct`, **floor** —
  mai sopra budget); poi `spot_qty = contratti × ct_val`, arrotondata a `spot_step`
  e ≥ `spot_min`. Delta atteso ≈ 0; tolleranza = 1 ct equivalente.
- Se `contratti < min_ct` o costo > budget → coppia **rifiutata con motivo** (non clampata).
- Apertura in sequenza: l'ordine delle coppie lo riceve il modulo (payback crescente);
  il modulo si ferma con motivo quando il capitale non basta più.
- Prezzi ≤ 0, input NaN/negativi → `ValueError`.

## Test richiesti (≥ 16, deterministici, con controllo non-vacuo)
- Arrotondamenti per tipo (dalla tabella docs/20): DOGE (ct_val 10, min 1 → 110 DOGE = 11 ct),
  ADA (10/1), DOT (1/1), LINK (1/1), XRP (1/1), AVAX (10/0.1), LTC (0.1/1) — attesi a mano.
- Budget: 4 coppie × 100 € con 850 € → tutte; con 500 € → 2 coppie + scartate con motivo.
- Rifiuti: sotto minimo strumento; step violato; input negativi/NaN; capitale nullo.
- Delta: esatto 0; oltre tolleranza → ko; al bordo tolleranza.
- Riconciliazione: tutto ok; una differenza; fill parziale.
- Chiusura: piano completo (perp→spot); stato chiuso → piano vuoto; spot senza perp → solo sell.
- Determinismo e proprietà: due run identici; su griglia di parametri mai output negativi.

## Consegna (stesso flusso del turno P10)
- Layout: `f2_repo/carry/carry_fase2.py` + `f2_repo/tools/tests/test_carry_fase2.py`
  (mirror del repo `alpha-omega-trading`; stile: vedi allegato `canary_carry.py`).
- Handoff in `/home/sergio/hermes_bridge/dsh-mc2/handoff/F2/`: i 2 file +
  `MANIFEST.txt` (sha256sum) + `LEGGIMI.md` + DONE nel canale `results.md`.
- Review Hermes con test rieseguiti; integrazione/esecuzione: Hermes (percorso denaro).
