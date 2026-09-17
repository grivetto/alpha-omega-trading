# 20 — La strada per triplicare: derivati su OKX EEA

Round 16. Il trend deployato e' long-only e su spot. Due limiti strutturali:
non guadagna nel bear market, e paga 0.70% per giro (taker 0.35% per lato), che
rende inutile qualsiasi timeframe piu' corto del giornaliero.

## 20.1 Cosa offre OKX EEA (verificato, sola lettura)

    mercati su eea.okx.com: 1425 spot, 482 swap, 215 future, 2434 opzioni
    fee derivate:           maker 0.02%  taker 0.05%
    fee spot (Lv1, reale):  maker 0.20%  taker 0.35%

**Sette volte meno.** Il round trip passa da **0.70%** a **0.10%**.

Ma l'account e' in modalita' semplice:

    acctLv: "1"          (spot; per i derivati serve 2+)
    enableSpotBorrow: false
    perm: read_only,trade

Quindi: i mercati CI SONO e i dati sono accessibili, ma **non si puo' tradare**
finche' l'account non viene portato ad acctLv 2 o superiore.

## 20.2 Perche' il costo decide tutto sul 4H

Stessa strategia, stessi parametri, stessi 19 asset, stesso periodo (2.4 anni),
su barre 4H. Cambia SOLO la fee. Griglia di 24 configurazioni
(canale 20/40/60/80 x ema 50/100/200 x long-only/long-short):

| misura | fee spot 0.35% | fee swap 0.05% |
|---|---|---|
| periodo intero, mediano | +16.04% | **+50.68%** |
| configurazioni positive | 24/24 | 24/24 |
| robuste (>= 4 finestre su 5) | **3/24** | **20/24** |
| long/short, periodo intero | +13.83% | **+61.06%** |
| long/short, robuste | 3/12 | **12/12** |

La stessa strategia passa da 3/24 a 20/24 configurazioni robuste **cambiando solo
la commissione**. E' la dimostrazione causale che sul 4H non era il segnale a
mancare: era il costo a mangiarselo.

## 20.3 Il giornaliero deployato, per confronto

Griglia identica sul GIORNALIERO a fee spot (quello che gira adesso):

    periodo intero, mediano +17.47%   positivo 18/24
    per blocchi,   mediano  -2.96%    robusto  0/24

Il rendimento di periodo c'e', ma **nessuna delle 24 configurazioni regge in 4
finestre su 5**. E' la conferma di quello che il round 15 aveva trovato: il
rendimento del giornaliero e' un EPISODIO, non un flusso. Il 4H a fee swap e'
l'unica cosa misurata che si comporta come un flusso.

Nota di metodo: il "composto per blocchi" moltiplica medie per-simbolo e non e'
un rendimento di portafoglio valido se i simboli rendono in modo molto diverso
(XLM +135% in un blocco, altri negativi). Per questo si riportano ENTRAMBE le
misure: il periodo intero da' la magnitudine, i blocchi danno la stabilita'.

## 20.4 Il costo che mancava: il funding

Su un perpetual si paga il funding ogni 8 ore. Misurato su 8 perpetual, ultimi
90 giorni:

    funding medio  0.0040% ogni 8 ore  ->  0.0119% al giorno
    su una tenuta media di ~3 giorni   ->  0.036%
    la fee swap per giro e'             0.10%

Quindi il funding vale circa **0.4x la fee**: il costo pieno per giro passa da
0.10% a ~0.136%, comunque **5 volte meno dello spot**. Non ribalta la
conclusione. Va detto che il funding e' mediamente POSITIVO (i long pagano, gli
short incassano): il long/short ne beneficia, il solo-long lo subisce.

## 20.5 Cosa serve per procedere

**Azione richiesta all'utente**: portare l'account OKX ad acctLv 2 (futures /
margin). Non e' qualcosa che posso fare io: e' una scelta di account, e su EEA
puo' dipendere dalla regolamentazione (MiCA). Va verificato con OKX.

Se l'upgrade e' possibile, il lavoro successivo e' a mia carico e va progettato,
non improvvisato:

1. **Short nel motore di produzione.** TrendPolicy oggi entra solo long. Serve
   l'ingresso simmetrico, con stop e trailing speculari (il motore di ricerca
   trend_ls e' gia' scritto e validato: il percorso long-only riproduce
   backtest_trend al bit).
2. **Cap di leva esplicito.** I derivati permettono leva 100x; il sizing attuale
   impegna ~17% di nozionale con rischio 2%. Va reso impossibile superare 1x,
   indipendentemente dai parametri.
3. **Quotatura USDT.** Gli swap sono su USDT, non su EUR: cambia la valuta di
   regolamento e introduce esposizione stablecoin.
4. **Ordini condizionali.** Sui derivati gli ordini stop esistono davvero: si
   puo' finalmente smettere di monitorare lo stop a mano.

## 20.6 Decisione di questo round

**Nessun cambio al deploy.** Il giornaliero resta quello che gira: e' positivo di
periodo e non c'e' alternativa spot migliore misurata (il 4H a fee spot e' 3/24
robusto, peggio). Il salto richiede l'upgrade dell'account, che e' una decisione
dell'utente.

Strumenti aggiunti: tools/trend_longshort.py (motore long/short validato),
tools/trend_4h_costi.py, tools/trend_4h_finestre.py, tools/trend_4h_griglia.py,
tools/trend_confronto_finale.py.
