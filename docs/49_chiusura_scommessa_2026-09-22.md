# 49 — Chiusura della scommessa asimmetrica: rientro in EUR sul master OKX

Data: 2026-09-22. Su richiesta del proprietario: *"mi servono i soldi indietro"*,
poi *"porta tutto il capitale in € sul main account di OKX"*.

## 49.1 Cosa è stato fatto, in ordine

| # | azione | esito |
|---|---|---|
| 1 | Sub-account OKX → master (EUR) | marcosub1 42,1191687893 + nuvolasub1 24,79284933230965 + mc2sub1 0,03016352341092 = **66,9421816450 EUR** spostati, 3 transfer `code=0` (transId 204894291/92/93) |
| 2 | Sweep del wallet scommessa su Base → indirizzo di deposito OKX | 2 transazioni firmate su mc2 (chiave mai uscita dall'host, mai stampata) |
| 3 | Accredito OKX | entrambi i depositi passati da `state 0` (in conferma) → `state 17` → **`state 2` (accreditato)** |
| 4 | Conversione in EUR sul master | ETH venduto su `ETH/EUR`, USDC venduto su `USDC/EUR` (ordini a mercato) |

## 49.2 Le transazioni on-chain (tracciabili)

| asset | importo | rete | txId | blocco | esito |
|---|---|---|---|---|---|
| USDC | 39,581987 | USDC-Base | `0x51bf777013638dbc3b33a149b1ac62b7c639a36e80c5de66409f02e15da9b57a` | 51653035 | OK (gas 57371) |
| ETH | 0,00324766 | ETH-Base | `0x94054d91fbc5d09a7bebec3f0a6865f15c8b726df91aa9e31a4a394aefb25d61` | 51653051 | OK (gas 21000) |

Destinazione: `0xeBa053e2726d156fcB12dc865Da76368658771C6` — indirizzo di deposito del
master letto dall'API e verificato **prima** della firma (USDC-Base ed ETH-Base coincidono).

depId OKX: USDC **601959007**, ETH **601959012**.

Nota operativa: il deposito è stato accreditato sul **trading account**, non sul
funding. L'endpoint `/api/v5/asset/balances` legge il funding e mostrava 0 mentre i
fondi erano già disponibili: la lettura corretta è `fetch_balance` (trading + funding).
La prima verifica (`state 17`, saldo 0) era quindi uno stato di attesa reale, non un
errore di lettura.

## 49.3 Riconciliazione finale

| voce | EUR |
|---|---|
| capitale dei sub-account | 66,9421816450 |
| scommessa convertita (USDC 34,6105 + ETH 7,7704) | 42,3809 |
| già presente sul master | 0,6700 |
| **totale sul master OKX** | **109,9930497311** |

Saldo finale verificato: `trading EUR 109,89304973107058` + `funding EUR 0,10`.

Costo dell'operazione: gas on-chain ~0,0000055 ETH (~0,013 EUR) + spread/fee delle
due vendite a mercato. La scommessa si chiude sostanzialmente in pari sul capitale
investito (42,44 EUR versati → 42,38 EUR rientrati).

## 49.4 Residui non recuperabili (dichiarati, non nascosti)

- **Wallet scommessa su Base**: 0,00002115 ETH (~0,05 EUR), tenuto per il gas. USDC 0.
- **Dust sul master OKX** sotto la precisione minima di vendita: ETH 6,515e-07,
  SOL 8,42e-07, ADA 8,32e-05, DOGE 8,42e-07 (frazioni di centesimo).
- **Dust sui sub-account**: mc2sub1 0,000986736 SOL (~0,15 EUR) + tracce di XRP/ADA/DOGE/UNI/ARB.
- **Kraken**: 0,4073 USD + 0,0053 EUR + dust ADA (~0,36 EUR). Non toccato: la fee di
  prelievo supera l'importo.

## 49.5 Ultimo miglio, che non è automatizzabile

Il prelievo **SEPA verso la banca** non è un'operazione da API: va fatto dal web/app
OKX con 2FA (o con banca già verificata). Da qui in poi il capitale è in un unico
posto, liquido in EUR, pronto per quel passaggio.

## 49.6 Stato del progetto dopo questa chiusura

- La **scommessa asimmetrica è chiusa**: wallet svuotato, nessun layer on-chain da
  scrivere, mandato "tetto di perdita 42 EUR / orizzonte 6-12 mesi" concluso.
- La **flotta di trading resta ferma** e i sub-account sono vuoti dell'EUR.
- Il capitale complessivo (~110 EUR) è sul master OKX: la decisione su cosa farne
  torna al proprietario (docs/48.5, punto 2: "li fermo o li tengo come banco di prova?").

## 49.7 Strumenti usati (in `.pytmp`, riutilizzabili)

`rientro_scommessa.py` (sweep, **dry-run di default**, `--go` per trasmettere),
`okx_pull.py` (sub → master), `okx_wait.py` (attesa accredito + conversione),
`okx_convert.py` (conversione in EUR), `okx_depositi.py` / `okx_dep_raw.py`
(diagnostica depositi), `check_tx.py` (stato transazione su Base),
`recon_rientro.py` / `recon_secrets.py` (ricognizione, sola lettura).

Regola rispettata: nessun movimento senza il via del proprietario; chiave privata mai
fuori da mc2 e mai stampata; ogni azione verificata con tx hash, depId e saldo prima/dopo.
