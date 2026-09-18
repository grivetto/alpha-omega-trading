# 47 — Metodo e cancello: da baracca a officina

Data: 2026-09-18. Su indicazione del proprietario: lista di fonti serie (freqtrade,
hummingbot, quantstart, hudsonthames, ml4trading, jesse, nautilus, BitMEX research,
Ernie Chan, Rob Carver, quantocracy; framework open source; dati onesti; doc
ufficiali exchange; ricerca accademica).

## 47.1 Cosa prendiamo, e cosa no

**Prendiamo (e perche'):**
- **freqtrade — lookahead-analysis**: il difetto che rende inutili i backtest. Da
  implementare come controllo obbligatorio, non come lettura.
- **jesse / ml4trading — walk-forward e cross-validation per serie temporali**:
  gia' fatto in parte, va reso sistematico.
- **Rob Carver (qoppac) — vol targeting, dimensionamento, portafoglio di molte
  scommesse piccole, modello di costo esplicito**. E' l'unica parte della lista che
  attacca il nostro problema vero: il rendimento episodico. NON l'abbiamo ancora
  provata.
- **nautilus_trader — architettura event-driven**: come riferimento per la
  struttura, non da adottare come dipendenza.
- **doc ufficiali exchange (OKX, Kraken, Bybit)**: rate limit, min_notional,
  idempotenza. Fonte primaria, piu' di cento blog.
- **Monte Carlo (jesse)**: per quantificare il rischio di sequenza, non solo il
  rendimento medio.

**Non prendiamo (e perche'):**
- **Market making (hummingbot)**: lo spread mediano degli alt su OKX e' **0,0778%**
  e su Bybit **0,1183%**, contro una fee maker di **0,10-0,20%** per lato. Catturare
  lo spread non e' possibile: si paga per fornire liquidita'. Chiuso dai numeri.
- **HFT / microstructure tick (tardis, cryptohftdata)**: servono latenza e
  colocazione che non abbiamo, e il conto e' di 42 EUR.
- **Pipeline ML (ml4trading)**: con 900-5.000 barre per serie non c'e' volume per
  addestrare niente che non sia overfitting. La parte utile del libro e' la
  validazione, non i modelli.
- **Qualunque cosa prometta rendimenti senza un modello di costo.**

## 47.2 La regola che cambia tutto: una flotta di CANDIDATI

Non si crea una flotta di bot che girano. Si crea una **flotta di candidati** che
passano o non passano **un solo cancello**, e solo i sopravvissuti vengono
deployati. Il cancello, per iscritto:

1. **Lookahead**: il segnale calcolato fino a t non cambia se aggiungo il futuro.
2. **Walk-forward**: rendimento positivo in ogni fold, non solo in media.
3. **Blocchi**: positivo in >= (blocchi-1) blocchi su blocchi uguali.
4. **Costo**: sopravvive a fee **+50%** rispetto a quella misurata.
5. **Monte Carlo**: bootstrap della sequenza dei trade; il 5o percentile non deve
   essere catastrofico.
6. **Universo**: il risultato regge anche togliendo i migliori 3 asset.

Chi non passa, non si deploya. Chi passa, entra in flotta. Questo e' "fare sul
serio": non piu' bot che girano per abitudine.

## 47.3 Il prossimo esperimento (l'unico non ancora provato)

**Trend a volatilita' targettizzata, portafoglio consapevole delle correlazioni,
universo largo.** Differenza rispetto a quanto gia' misurato: non si dimensiona a
rischio fisso per trade, si targettizza la volatilita' del portafoglio, e i pesi
tengono conto della correlazione. E' il punto di Carver che non abbiamo toccato, e
attacca direttamente l'episodicita' misurata in docs/43.

Misurato con il cancello di 47.2, sugli stessi dati (77 serie 4H, 56 serie 1D).
Se non passa, la risposta e' no — e sara' un no con i numeri.

## 47.4 Stato della scommessa asimmetrica

Wallet creato e verificato: 0x8788D169201cb0D8E5b355e26924c9D3D51ad810, seed
indipendente, tetto 42 EUR. In attesa di: backup della chiave da parte del
proprietario, whitelist su OKX, poi prelievo. Il layer di esecuzione on-chain resta
da scrivere (0 righe oggi).
