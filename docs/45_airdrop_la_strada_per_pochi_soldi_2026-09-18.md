# 45 — Con pochi soldi: la strada giusta non e' il trading

Data: 2026-09-18.

## 45.1 Il tetto del trading a 109 EUR, misurato

| lettura | rendimento | su 109 EUR |
|---|---|---|
| backtest 2,4 anni (dominato da un rally) | +14,44% CAGR | +16 EUR/anno |
| regime recente, 365 barre | +8,37% | +9 EUR/anno |
| prudente | +5% | +5 EUR/anno |

Drawdown atteso 13-17%. **Il tetto e' 5-16 EUR l'anno.** Non e' un problema di
strategia: docs/18, 34, 39, 40 e 43 hanno chiuso fee, venue, ensemble, stagionalita'
e drift. E' aritmetica: il rendimento e' una **percentuale**, e su 109 EUR una
percentuale grande e' comunque una cifra piccola.

Per fare 100 EUR/anno su 109 EUR servirebbe +92%/anno. Non esiste evidenza che
questo sistema ci arrivi, e inseguirla significherebbe alzare il rischio fino a
distruggere il conto.

## 45.2 Quello che invece esiste gia' su questa macchina: la cartella airdrop-farm

Un progetto separato, scritto a luglio, con una tesi opposta e corretta:

> **Scommessa asimmetrica: perdi al massimo 100 EUR, puoi guadagnare 1.500-80.000.**
> Budget 100 EUR, 20 wallet, 4 chain, 6-12 mesi, nessun guadagno giornaliero.

E' **esattamente** il sistema "con pochi soldi che guadagna": li' il capitale non e'
il vincolo, il lavoro si'. E il budget dichiarato (100 EUR) coincide con quello che
oggi sta nella flotta di trading.

## 45.3 Ma lo stato reale non e' quello del DESIGN

Audit di oggi su mc2:

| cosa | stato vero |
|---|---|
| righe totali | 2.475 |
| strategie (airdrop, hyperliquid, yield, mexc) | 51-65 righe ciascuna = **scheletro** |
| connettori chain (base, scroll, linea, abstract, monad) | **28-36 righe** = stub, nessuna firma/broadcast reale |
| activity.db | fermo al **25 luglio**, nessuna attivita' on-chain |
| servizi | airdrop-farm-MARCODG1.service **disabled**, mai avviati |
| timeline del DESIGN | "5 agosto: 100 EUR su Kraken -> Base; 6 agosto: avvio" — **non e' mai successo** |

Quindi non e' un sistema da riavviare: e' un **progetto mai partito**, con un
simulatore e una buona architettura. Onestamente: 0 righe di esecuzione on-chain.

## 45.4 Due difetti del DESIGN, da correggere prima di scrivere codice

1. **Il seed unico per 20 wallet e' la firma dello sybil.** Il DESIGN lo chiama
   "isolamento wallet", ma 20 wallet derivati dallo stesso seed sono correlati per
   costruzione: e' esattamente il pattern che i filtri cercano. Il Poisson timing
   non lo nasconde. Servono **seed indipendenti** (o, meglio, pochi wallet per seed
   con finanziamenti e pattern separati), accettando che siano meno di 20.
2. **La lista delle chain e' vecchia di due mesi.** Verifica di oggi: **Scroll ha
   gia' lanciato il token e distribuito l'airdrop** (7% della supply), e **Linea ha
   gia' avuto la sua distribuzione**. Restano vive le chain **senza token**, e la
   candidata principale e' **Base** — ma Base ha annunciato **strumenti anti-bot
   on-chain** e un requisito di **staking per gli account nuovi** prima di ottobre.
   Cioe': la finestra su Base si sta chiudendo e si sta chiudendo *contro* il
   multi-wallet. Non si puo' scrivere codice su una lista di chain non verificata.

## 45.5 Il piano corretto

1. **Verificare, prima di programmare**: quali chain sono ancora senza token e
   ancora aperte, per ciascuna quali requisiti anti-sybil, quanto gas serve. Una
   giornata di ricerca, non un mese di codice su bersagli morti.
2. **Ridurre l'ambizione all'onesta'**: non 20 wallet su 4 chain. **Pochi wallet
   indipendenti su 1-2 chain vive**, con budget 50-100 EUR e tetto di perdita
   scritto.
3. **Implementare l'esecuzione vera** solo dopo (1) e (2): connettori con firma
   locale, invio transazione, verifica on-chain, gestione gas, idempotenza. E'
   il pezzo che oggi non esiste.
4. **La cifra in euro e' secondaria**: il valore atteso dichiarato (7.000 EUR) e' un
   *piano*, non una misura. Le probabilita' del DESIGN (30% nessun airdrop) sono
   credibili come ordine di grandezza della varianza, non come previsione.

## 45.6 La scelta, in una riga

Gli stessi **109 EUR** che nel trading rendono **9 EUR l'anno** sono il **budget da
100 EUR** di un progetto scritto apposta per fare dell'asimmetria con pochi soldi.
Il trading non ha piu' niente da dire a questa cifra: e' stato misurato fino in
fondo. La prossima riga di lavoro utile non e' un'altra strategia di prezzo — e'
verificare dove lo sybil non e' ancora stato chiuso, e andarci con pochi wallet
fatti bene.
