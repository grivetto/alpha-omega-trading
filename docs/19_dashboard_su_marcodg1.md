# 19 — Dashboard e Zabbix su MARCODG1 (fuori dal CGNAT)

## 19.1 Il problema

Dashboard e Zabbix erano serviti dal tunnel Cloudflare che parte da **mc2**, la
macchina di casa, **dietro CGNAT**. Tutta la presenza pubblica dipendeva dalla
linea di casa: se cadeva, cadevano anche dashboard e Zabbix.

Prove raccolte prima di intervenire: il tunnel home-cgnat aveva **46** righe di
errore/retry/disconnessione in 7 giorni, e il servizio dashboard **45**
start/stop. Non era un sospetto: era misurabile.

## 19.2 La nuova architettura

Il punto di ingresso pubblico di tutto cio' che riguarda Denaro e' ora
**MARCODG1**, un VPS con IP pubblico, dove gia' giravano l'aggregator completo e
il server Zabbix.

    web.grivetto.eu        -> tunnel denaro-marcodg1 -> 127.0.0.1:8913 (dashboard)
    denaro.grivetto.eu     -> idem
    denaro-api.grivetto.eu -> 127.0.0.1:8912 (aggregator JSON)
    zab.grivetto.eu        -> 127.0.0.1:1080 (Zabbix)

Il tunnel home-cgnat su mc2 **resta** per i servizi che devono stare a casa
(ssh, home, freellmapi, agent-zero, zabbix.grivetto.eu). La separazione e' netta:
a casa cio' che e' di casa, su un VPS cio' che deve essere sempre raggiungibile.

Componenti nuovi su MARCODG1:
- denaro-dashboard-marcodg1.service (:8913) — serve l'HTML e fa da proxy al JSON,
  con cache last-good;
- cloudflared-denaro.service — tunnel dedicato, config **locale e versionata**
  (/home/marco/.cloudflared/denaro.yml), non gestita a mano dalla dashboard
  Cloudflare.

## 19.3 L'aggregator di MARCODG1 ora e' il repo

MARCODG1 eseguiva /home/marco/denaro/infra_aggregator.py, una **copia separata**
che diceva cose diverse dal repo: 25 bot invece di 15, con Kraken e i fossili
trend-live. Un drop-in override la fa ora puntare al file del repo: una sola
fonte di verita'.

Due difetti trovati in questo passaggio:

1. sorgenti_conti() usava l'IP nudo per nuvola. Da mc2 funzionava perche'
   l'utente e' sergio; da MARCODG1 l'utente e' marco, quindi ssh tentava
   marco@87.106.3.15 e **24.83 EUR sparivano** dal totale (49.75 invece di
   74.58). Ora e' sergio@87.106.3.15.
2. infra_snapshot.py duplicava ~130 righe di logica e usava
   collect_node_bots() invece di collect(): la dashboard pubblica serviva 25 bot
   mentre il percorso live ne serviva 15. Ora lo snapshot **e'** la risposta di
   collect().

## 19.4 Autohealing: da "raccolto ma muto" a vigilante

Gli item svc.<unit> venivano pushati dal cron di MARCODG1 ma **non avevano
nessun trigger**: un servizio morto restava morto finche' qualcuno non apriva la
dashboard. Inoltre la lista sorvegliava unit **inattivi** (denaro-node-nuvola) e
citava unit **inesistenti** (zabbix-tunnel).

Ora: 18 servizi realmente attivi su 3 macchine, con 36 trigger (uno per
"non in esecuzione", uno per "nessun dato da 10m").

Due difetti dell'healer, trovati con una prova end-to-end:

1. **ssh mangiava lo stdin del ciclo.** handle_problem gira dentro un while read
   alimentato da una pipe; il comando di restart consumava lo stdin e **il ciclo
   terminava dopo il PRIMO problema**. Con piu' guasti contemporanei, ogni ciclo
   ne curava uno solo. Corretto con la redirezione da /dev/null.
2. **Riavvio del servizio sbagliato.** Il trigger nomina il unit
   (SERVIZIO <unit>: ...), ma l'healer mappava solo host -> servizio: un guasto
   sulla dashboard avrebbe riavviato il **nodo di trading**. Ora il unit viene
   estratto dal trigger e si riavvia quello.

Terzo difetto, nel pusher: su **una singola** lettura SSH fallita veniva pushato
status=0, facendo sembrare morto un bot vivo. E' cosi' che il 2026-09-17 un
hiccup di rete ha riavviato denaro-node-nuvola-trade (trigger nuvola_dot). Ora una
lettura fallita non pusha nulla: decide il trigger "nessun dato" (5 minuti di
silenzio), non un singolo campione.

## 19.5 Prova end-to-end

1. systemctl stop denaro-dashboard-marcodg1
2. Zabbix rileva: "SERVIZIO denaro-dashboard-marcodg1: non in esecuzione"
3. L'healer: "servizio nominato dal trigger: denaro-dashboard-marcodg1" ->
   "RIAVVIO [MARCODG1] denaro-dashboard-marcodg1" -> "OK"
4. Servizio di nuovo active; web.grivetto.eu e zab.grivetto.eu rispondono 200.

Il servizio e' stato riavviato **da solo**, senza toccare il nodo di trading.
