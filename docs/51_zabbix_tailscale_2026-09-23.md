# 51 — Zabbix su rete Tailscale: agent delle 3 macchine dietro CGNAT

Data: 2026-09-23. Richiesta del proprietario: *"configura gli zabbix agent delle 3 macchine
perché lo zabbix server ha un IP dietro rete CGNAT quindi non ha un IP pubblico fisso"* →
*"si potrebbe monitorare le macchine su rete Tailscale"*.

## 51.1 Il guasto reale, misurato

Il server Zabbix gira **su mc2** (`zabbix-server`, `zabbix-web`, `zabbix-db` in docker,
trapper su `0.0.0.0:10051`, web su `:1080`). mc2 non ha un indirizzo pubblico stabile: esce
su Internet via **VPN Surfshark**, che assegna IP diversi nel tempo (visti: `84.17.58.196`,
`84.17.58.208`).

Gli agent di nuvola e MARCODG1 avevano in allowlist solo `127.0.0.1`, `46.102.64.0/20`
(vecchio IP dell'ISP) e il prefisso IPv6 di casa. Risultato: **ogni check passivo rifiutato**,
una volta al minuto, per ore:

```
failed to accept an incoming connection: connection from "84.17.58.208" rejected,
allowed hosts: "127.0.0.1,46.102.64.0/20,2a04:1240:3200:fd00::/64"
```

Lato server, entrambe le interfacce risultavano **`available=2`**:

```
nuvola     iface 87.106.3.15     avail=2  Received empty response from Zabbix Agent ...
MARCODG1   iface 87.106.222.123  avail=2  Received empty response from Zabbix Agent ...
```

Non è un problema da poco: i tre host hanno **48-80 item "Zabbix agent" (passivi)** ciascuno —
la parte principale del monitoraggio.

Due workaround precedenti, entrambi inefficaci:

- `ServerActive=...,46.102.64.116`: indirizzo dell'ISP **non più raggiungibile**
  (`timeout` nei test da nuvola e MARCODG1).
- `zabbix-tunnel-reverse.service` (autossh `-R 10051` verso MARCODG1): il forward remoto
  **si lega al loopback di MARCODG1** (`127.0.0.1:10051`), quindi non è mai stato utilizzabile
  dagli agent di altre macchine.

## 51.2 La soluzione: Tailscale come trasporto

Tailscale era **già installato e attivo** su tutte e tre le macchine (e su altre della tailnet):

| nodo | IP tailnet |
|---|---|
| mc2 (server Zabbix) | **100.87.24.42** |
| nuvola | 100.103.169.99 |
| MARCODG1 | 100.70.254.121 |

Test di raggiungibilità prima di toccare le configurazioni:

- agent → server: `100.87.24.42:10051`, `:1080`, `:22` **aperti** da nuvola e da MARCODG1;
  `46.102.64.116:10051` **timeout**, `87.106.222.123:10051` **rifiutato**.
- server → agent: dal container `zabbix_get` verso `100.103.169.99:10050` e
  `100.70.254.121:10050` rispondeva `ZBX_NOTSUPPORTED ... dropped connection because of access
  permissions` — cioè **la rete funzionava, mancava solo il permesso** nell'allowlist.

Dettaglio che rende il disegno pulito: il container del server esce **mascherato con l'IP
tailnet dell'host** (`100.87.24.42`), quindi la sorgente dei check passivi diventa **stabile**
— confermato dal log di MARCODG1 prima della patch:
`connection from "100.87.24.42" rejected, allowed hosts: ...`.

## 51.3 Cosa è stato cambiato

**a) Config degli agent** (`/etc/zabbix/zabbix_agentd.conf`, con backup timestampato):

| host | `Server=` (check passivi) | `ServerActive=` (check attivi) | `Hostname=` |
|---|---|---|---|
| nuvola | `127.0.0.1,46.102.64.0/20,2a04:...::/64,100.87.24.42` | `127.0.0.1:10051,100.87.24.42:10051` | `nuvola` (invariato) |
| MARCODG1 | `127.0.0.1,46.102.64.0/20,2a04:...::/64,100.87.24.42` | `127.0.0.1,100.87.24.42:10051` | `MARCODG1` (invariato) |
| mc2 | `127.0.0.1,192.168.1.99,172.21.0.0/24,100.87.24.42` | `127.0.0.1,172.21.0.4,192.168.1.99,100.87.24.42:10051` | `mc2` (**aggiunto**, prima assente) |

Backup: `zabbix_agentd.conf.bak.tailscale.20260923_195222` (nuvola),
`..._215235` (MARCODG1), `..._215239` (mc2). Gli indirizzi morti dell'ISP tolti da
`ServerActive`; le voci esistenti in `Server=` sono state **mantenute** (non tolgono nulla e
restano come rete di sicurezza).

**b) Interfacce dei host in Zabbix** (via API `hostinterface.update`), così i check passivi
viaggiano sulla tailnet e non sull'IP pubblico dell'agent:

| host | interfaccia prima | interfaccia dopo (interfaceid) |
|---|---|---|
| nuvola | 87.106.3.15 | **100.103.169.99** (32) |
| MARCODG1 | 87.106.222.123 | **100.70.254.121** (36) |

mc2 resta su `192.168.1.99` (il container raggiunge l'host così, e funziona: `avail=1`).

## 51.4 Verifica (non "dovrebbe funzionare": misurato)

Check passivi eseguiti **dal container del server** dopo il riavvio degli agent:

```
docker exec zabbix-server zabbix_get -s 100.103.169.99 -k agent.ping  -> 1
docker exec zabbix-server zabbix_get -s 100.70.254.121 -k agent.ping  -> 1
docker exec zabbix-server zabbix_get -s 192.168.1.99   -k agent.ping  -> 1
(system.uptime su nuvola -> 1281140)
```

Stato in Zabbix dopo il giro di polling:

| host | iface_avail | item passivi aggiornati negli ultimi 5 min |
|---|---|---|
| nuvola | **1** (era 2) | 48 / 56 |
| MARCODG1 | **1** (era 2) | 42 / 56 |
| mc2 | 1 | 63 / 80 |

Dati che scorrono davvero (esempi): nuvola `Context switches per second` 1s fa, `System
uptime` 1s fa; MARCODG1 `Total memory` 19s fa. **Nessun rifiuto** negli agent dopo il cambio
degli indirizzi (ultimo: 19:52 su nuvola, 21:52 su MARCODG1, entrambi precedenti).

## 51.5 Cosa NON è stato toccato, e perché

- **`zabbix-tunnel-reverse.service`**: resta com'è. È ancora vivo e serve la **web UI**
  (MARCODG1 `127.0.0.1:1080`, inoltrata a mc2) e la **porta SSH di emergenza**
  (MARCODG1 `127.0.0.1:2222` → mc2:22). Il suo forward `10051` è ormai inutile (e comunque
  legato al loopback), ma toccarlo significherebbe riavviare l'unit e rischiare quei due
  servizi: non ne vale la pena. Nota: nel journal ci sono tentativi falliti di riavvio
  (`bind [127.0.0.1]:8912: Address already in use`, `remote port forwarding failed for listen
  port 10051`) — sono di sessioni sovrapposte, la sessione attiva tiene le porte da un giorno.
- **Item/trigger/template**: nessuna modifica. Sostituire l'indirizzo dell'interfaccia è
  trasparente per item, template e dipendenze.

## 51.6 Conseguenze e punti di attenzione

1. **Il monitoraggio della flotta ora dipende da Tailscale** su mc2 e su ogni agent. Se
   `tailscaled` si ferma, i check passivi si fermano (i trapper locali e la web UI locale no).
   Vale la pena tenere un trigger/monitor su `tailscaled` stesso, o sullo stato "available"
   dell'interfaccia, per non tornare al caso di oggi in silenzio.
2. **La web UI è raggiungibile dalla tailnet**: `http://100.87.24.42:1080/` (verificato aperto
   da nuvola e MARCODG1). Utile per non dipendere dal tunnel SSH.
3. **L'IP tailnet del server (100.87.24.42) è ora un dato di configurazione** in tre file
   `zabbix_agentd.conf` e in due interfacce Zabbix. Se mc2 venisse rimossa e ri-aggiunta alla
   tailnet, quell'indirizzo cambierebbe e andrebbe aggiornato nei quattro punti (gli script in
   `.pytmp` lo fanno con `--server-ip`).
4. **CGNAT e VPN restano**: non c'è più dipendenza dall'IP pubblico per Zabbix, ma il traffico
   Zabbix ora esce/entra dalla tailnet (WireGuard, cifrato) — non dalla VPN Surfshark. Questo
   è anche il motivo per cui il problema Groq di docs/50 resta un problema separato.

## 51.7 Come si torna indietro

- Agent: copiare i backup `zabbix_agentd.conf.bak.tailscale.<ts>` e riavviare `zabbix-agent`.
- Zabbix: rimettere le interfacce a `87.106.3.15` (nuvola, interfaceid 32) e
  `87.106.222.123` (MARCODG1, interfaceid 36), oppure rilanciare
  `zabbix_iface_update.py` modificando la mappa `NUOVI`.
- Script usati (in `.pytmp`, dry-run di default, mai `--go` implicito):
  `agent_tailscale_patch.py`, `zabbix_iface_update.py`, `zabbix_recon.py`,
  `zabbix_verifica2.py`, `conn_test.py`.
