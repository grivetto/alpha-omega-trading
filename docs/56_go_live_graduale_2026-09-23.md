# 56 — Go-live graduale: come si prova un esecutore senza bruciare capitale

Data: 2026-09-23. Voce (4) dell'obiettivo. Dipende da `docs/53` (§0.6, i difetti che bloccano la
riapertura), `docs/54` (dimensionamento) e `docs/55` (requisiti dell'esecutore).

**Principio di partenza**: il difetto di fondo di questo progetto non è la strategia. È che il
percorso di esecuzione **non è mai stato esercitato con denaro vero** — la fase trend deployata ha
fatto 0 trade reali (`docs/37:85`, `docs/41:96`) e contiene tre difetti che possono distruggere
capitale. Quindi il go-live non è "accendere i bot": è **comprare informazione sull'esecutore**,
pagando il meno possibile.

---

## 56.1 Il vincolo che decide il disegno: la strategia è lentissima

Il trend giornaliero fa **~10 trade per asset in 2,5 anni** (`docs/17:576`), cioè **~4 trade per
asset all'anno**. Su 17 asset la flotta produce quindi **~68 trade l'anno, ~1,3 a settimana**.

Ne segue una cosa che cambia il piano:

> **Non si valida un esecutore partendo da un solo asset.** Quel bot potrebbe non fare nessun
> trade per mesi, e resteremmo con zero informazione e il capitale fermo.

## 56.2 La regola: si scala il CAPITALE, non il numero di asset

La gradualità serve a limitare il **denaro a rischio**, non l'attività. Quindi si tiene la flotta
completa — è lei che genera i segnali — e si tiene minuscola la **dimensione** di ogni posizione,
al minimo che la sede accetta.

| stadio | asset | capitale impegnato | cosa compra | durata tipica |
|---|---|---|---|---|
| 0 | — | 0 € | la meccanica: decisioni, stato, health, curva equity | giorni |
| 1 | 1 | ~3 € (un trade forzato) | il giro completo ordine→fill→stop→uscita→fee | 1 giorno |
| 2 | 17 | ~50 € impegnati | il comportamento su segnali veri, a dimensione minima | ~6 settimane |
| 3 | 17 | 1.000 € | l'economia vera, con il cap di esposizione | continuo |

## 56.3 Gli stadi, con criteri verificabili

### Stadio 0 — Meccanica in dry-run, zero denaro
- **Precondizione**: nessuna. Si può fare subito.
- **Cosa si guarda**: che il bot prenda, su barre reali, le **stesse** decisioni del backtest;
  che lo stato non diverga dall'exchange; che `EquityTracker` diventi `warm` e produca numeri.
- **Criterio di uscita**: N giorni di dry-run in cui ogni decisione è confrontata con il
  backtest sulle stesse barre, e le differenze sono **zero o spiegate**.
- **Criterio di stop**: qualunque divergenza non spiegata fra dry-run e backtest.
- **Nota**: il dry-run di un motore proprio non è mai fedele come quello di un framework che lo
  dichiara tale (`docs/55` §55.3). Va quindi *verificato*, non assunto.

### Stadio 1 — Un trade minimo, forzato a mano
- **Precondizione**: stadio 0 chiuso; R1/R2/R3 chiusi con i 9 test verdi.
- **Cosa si fa**: si apre **deliberatamente** una posizione di dimensione minima su **un** asset
  (≈3 €, cioè 3× il `min_notional`), senza aspettare un segnale, e si lascia che sia **il
  sistema** a gestirla: stop, trailing, uscita.
- **Perché forzato**: aspettare un segnale su un asset significa aspettare mesi (§56.1). Il
  percorso di uscita è esattamente ciò che non è mai stato provato, ed è dove stanno R1 e R2.
- **Criterio di uscita**: un documento con **ordine, fill, stop piazzato, uscita, fee pagata e
  slittamento misurati**, confrontati con il modello — riusando `tools/verifica_trade` e il
  verificatore già in `tools/` (commit `5489d68`).
- **Criterio di stop**: qualunque scostamento fra ciò che il sistema crede di aver fatto e ciò
  che risulta dal conto.

### Stadio 2 — Flotta completa a dimensione minima
- **Precondizione**: stadio 1 chiuso con il documento.
- **Cosa si guarda**: il comportamento sui segnali veri — quante posizioni si aprono, se lo stop
  scatta davvero, se due bot sullo stesso conto si danneggiano (è il raggio d'azione di R1), se
  il cap di esposizione tiene.
- **Perché la flotta intera**: ~1,3 trade a settimana fleet-wide significano una manciata di
  trade reali in ~6 settimane, **inclusi probabilmente eventi di stop** — che è l'unico modo di
  esercitare davvero R1 e R2.
- **Criterio di uscita**: almeno un evento di stop reale gestito correttamente, più la
  riconciliazione fra stato del bot e saldo reale su **tutti** i bot.
- **Criterio di stop**: una sola divergenza non spiegata fra stato e conto.

### Stadio 3 — Capitale pieno
- **Precondizione**: stadi 0-2 chiusi; cap di esposizione di conto attivo e verificato (Q6);
  quota per bot applicata in tutti i config (`docs/54` §54.1).
- **Cosa si guarda**: l'economia vera. E il pedaggio, che è il vincolo misurato in `docs/17`.
- **Criterio di stop**: drawdown oltre il limite configurato, o una divergenza di riconciliazione.

## 56.4 Quanto costa la validazione

Trascurabile, e vale la pena dirlo perché toglie l'alibi:

- **Stadio 1**: una posizione da 3 €, andata e ritorno a 0,778% → **~0,02 €**.
- **Stadio 2**: ~50 € impegnati, ~8 trade in 6 settimane, posizioni da 2-3 € → **~0,2 €**.

**Il costo della validazione non è il problema. Il rischio da evitare è il dimensionamento** —
un bug come R1 su un conto con 1.000 € non costa 0,02 €, liquida il conto.

## 56.5 Il kill switch

Serve un modo di fermare tutto che non dipenda dal bot che si vuole fermare:

- **per simbolo**: il bot non apre nuove posizioni e chiude la sua (non "tutto l'asset": R1);
- **per flotta**: un interruttore unico che ferma l'apertura su tutti e lascia gestire le
  posizioni esistenti;
- **chi decide**: il proprietario. Nessun agente ferma o riapre la flotta di sua iniziativa.

## 56.6 Cosa NON si fa

- **Non si riapre il live per verificare se i difetti sono reali.** Si chiudono i difetti, e poi
  si verifica. (Già in `docs/53`.)
- **Non si valida su un solo asset** aspettando un segnale: è non misurabile (§56.1).
- **Non si passa allo stadio successivo senza il criterio di uscita** dello stadio precedente.
  Il criterio è la prova, non il tempo trascorso.
- **Non si aumenta il capitale per "compensare"** un risultato deludente: la dimensione
  moltiplica l'edge, non lo crea.

## 56.7 Cosa manca perché questo piano parta

| manca | dove |
|---|---|
| R1/R2/R3 corretti e i 9 test verdi | `application/` — bloccato dall'accordo con Hermes |
| Un dry-run di cui sia dichiarata la fedeltà | dipende dall'esecutore scelto (`docs/55` §55.3) |
| Cap di esposizione di conto (Q6) | `domain/` + `application/` |
| Quota per bot nei config | `config/` — patch pronta in `tools/audit_capitale_config.py` |
| Un modo di forzare un trade minimo in sicurezza | da scrivere, e va approvato dal proprietario |
