fix(telemetria): snapshot autonomo e onesto + scoperto un conto non presidiato da 25,52 EUR

Seguito di 4073fb7. Due cose.

1) infra_snapshot.py e' la fonte che la dashboard pubblica legge davvero
(l'aggregatore serve lo snapshot pre-generato dal cron ogni minuto). La sua
logica dei totali era duplicata e divergeva da quella dell'aggregatore:
- node_total_pnl sommava i bot PAPER (equity virtuali) al PnL reale;
- i bot con health vecchio contavano come "running".
La dashboard pubblica mostrava +74,99 EUR di PnL contro ~-0,30 reali.
Ora lo snapshot calcola i totali in modo autonomo (non importa funzioni
dall'aggregatore: il cron deve restare indipendente) con live/paper separati e
stale esclusi. Verificato in produzione su MARCODG1:
    node_total_pnl: 0.0   (prima 74.99)
    node_paper_pnl: 47.99 (voce separata)
    node_live_bots: 0  node_paper_bots: 7
    node_stale_bots: elenco esplicito dei nodi spenti

2) Il breakdown dei saldi ha rivelato un conto che l'analisi precedente dava
per inerte: OKX nuvolasub1, 25,52 EUR (19,04 EUR + 0,0755 SOL), con una sell
SOL@90,89 aperta dal 2026-09-11 che blocca tutto il SOL. La chiave valida sta
in /home/sergio/denaro/.env su nuvola; quella in
/home/sergio/alpha-omega-trading/.env e' invece invalida (50111): due .env
sulla stessa macchina, uno buono e uno no. Il capitale NON era perso, ma non
era contato.

Nota di trasparenza: durante la deduplicazione ho rotto lo snapshot in
produzione per alcuni minuti (il cron chiamava una funzione non ancora
presente nell'aggregatore deployato). Riparato nella stessa sessione rendendo
lo snapshot autonomo e verificato.
