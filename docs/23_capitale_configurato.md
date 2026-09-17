# 23 — Il capitale configurato era rimasto indietro (round 21)

## 23.1 Il difetto

Leggendo i notional attesi dal controllo live: TRX risultava **17.21 EUR**.
Quella cifra corrisponde a un budget di **24.90 EUR**, non ai **42.12** che il
conto ha davvero.

Causa: la policy dimensiona con

    budget = min(capital_config, saldo_libero)

e i config dicevano ancora capital: 24.9 (mc2) e 24.81 (marcodg1) — le cifre di
quando i conti avevano quel saldo. Dopo il deposito a 42.12 e 42.04, i bot
continuavano a dimensionare su ~24.9: **il 41% del capitale restava fermo**.

Non era solo denaro inutilizzato: la produzione non corrispondeva piu' a cio' che
e' stato misurato. Tutte le simulazioni di questa sessione passavano il SALDO
INTERO come capitale, quindi il rendimento misurato (+73.04% di periodo, Sharpe
1.39) presuppone che il saldo sia impiegabile.

## 23.2 La correzione

    mc2       24.90 -> 42.12   (7 bot)
    nuvola    24.83 -> invariato (era gia' corretto)
    marcodg1  24.81 -> 42.04   (4 bot)

Verificato dopo il riavvio: i notional attesi sono cresciuti di ~69% su mc2 e
marcodg1 (TRX 17.21 -> 29.10, BTC 8.69 -> 14.71, ADA 3.89 -> 6.59), il rischio
per trade e' tornato al 2% del capitale reale come da progetto.

## 23.3 La concentrazione che ne deriva

Con il capitale corretto, TRX arriva a **29 EUR su un conto da 42 (69%)**. Non e'
un errore di sizing: TRX ha ATR all'1.45%, quindi lo stop e' al 2.9% e la size
sul rischio diventa grande. Il rischio a stop resta il 2% del capitale.

Ma il backtest assume di essere servito AL PREZZO di stop. Una GAP che salta lo
stop colpisce l'intera posizione: -10% su 29 EUR sono 2.9 EUR, cioe' il 6.9% del
conto invece del 2% previsto.

Misurato con il simulatore validato, il tetto per posizione (max_exposure):

    tetto   rendimento   maxDD   Sharpe   12 mesi
    100%      +73.04%     7.16%    1.39    +9.17%
     50%      +72.54%     6.97%    1.39    +8.03%
     40%      +69.36%     7.07%    1.41    +7.35%
     33%      +65.12%     7.29%    1.45    +6.82%

Il tetto al 50% costa **0.50 punti** su 2.4 anni; al 40% ne costa 3.68. **Non
applicato**: la misura dice che un costo c'e', e il beneficio (le gap) non e'
modellato dal backtest.

## 23.4 Un limite dichiarato

Ho provato a misurare il rischio di gap costruendo un simulatore con una gap
avversa sulle uscite a stop. **Non riproduce quello validato**: a gap zero dava
+69.01% dove il validato da' +64.21%, e i conteggi dei trade differiscono (BTC 13
contro 11). Un simulatore che non riproduce quello di riferimento non puo'
decidere nulla, quindi i suoi numeri **non sono stati usati**.

Resta un'indicazione qualitativa (con gap del 2% il rendimento di periodo scende
da +73% a +57%, con gap del 5% a +35%) che pero' va presa come ordine di
grandezza, non come misura.

Conclusione operativa: la concentrazione e' un rischio NOTO e DOCUMENTATO, non
coperto da una misura affidabile. Il tetto resta disponibile come parametro
(max_exposure) se si vorra' applicarlo per prudenza.
