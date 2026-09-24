# 60 — Incidente di sicurezza sulla flotta: miner su MARCODG1 (contenuto il 2026-09-25)

Questo documento è il verbale di un incidente **reale e verificato**, trovato durante l'audit della
flotta del 25/09/2026. Non è trading: è la premessa del trading. Una macchina che mina crypto per
conto di terzi non è una macchina su cui far girare capitale.

---

## 60.1 Cosa è stato trovato

**Host:** MARCODG1 (87.106.222.123, utente `marco`, 3,8 GB RAM).

| reperto | valore |
|---|---|
| processo | PID 1156957, utente **`zabbix`**, avviato **dom 20 set 21:24:01**, 4 giorni di attività |
| binario | `/var/tmp/.X11-unix-socket/.kworker_sys` — ELF 64-bit statico, stripped, 6.665.112 byte |
| md5 | `b091dfd22c9f28833d8e7449b678b743` |
| nome falsificato | in `/proc/1156957/status`: `Name: kworker/u4:2` (nome di thread del kernel, ma processo utente) |
| consumo | **199% CPU, 2.135.240 KB RSS (53,9% della RAM)**, swap 1.624 MB usati |
| connessione | `ESTAB 87.106.222.123:56430 → 57.129.119.218:33333` — la 33333 è porta tipica di pool di mining |
| persistenza | crontab utente `zabbix`: `* * * * *` **e** `@reboot` che rilanciano il binario |
| artefatto accessorio | `/var/tmp/.X11-unix-socket/.self`, md5 `bb097d04488c998ef50f16233c8eca40`, che cita un secondo binario **`.lpe_core`** (*local privilege escalation*) oggi assente |

**Droppato il 19 settembre 2026 fra le 20:43 e le 20:47; in esecuzione dal 20 settembre alle 21:24.**

### Impatto diretto sul trading (nessuna ipotesi, è nei log)

Il nodo live su MARCODG1 (`denaro-node-marcodg1-xrp`) registra **32 oscillazioni di SafeMode in 24
ore**, ping-pong `→ safe (RAM 87%)` / `→ caution (RAM 84%)`. Il miner occupava oltre metà della RAM.
La macchina stava degradando il trading perché stava minando per terzi.

---

## 60.2 Era su più macchine

| host | reperto | stato |
|---|---|---|
| **MARCODG1** | crontab `zabbix` **attivo** con il payload; binario presente ed eseguito | **contenuto** |
| **mc2** | crontab `zabbix` **svuotato** il **19 set 20:43:51** tramite `/dev/shm/.cron_clean_421586` (l'artefatto è stato poi cancellato); `/var/tmp/.syslog-e129b042/.daemon.lock` di proprietà `zabbix`, 22 set | nessun processo attivo, nessuna connessione a pool |
| **nuvola** | nessun crontab `zabbix`, nessun file droppato, nessun processo sospetto | pulita |

La coincidenza dei timestamp (**19/09 20:43**) su due macchine diverse indica un'azione singola su
più host, non due incidenti indipendenti.

---

## 60.3 I due vettori (le cause, non i sintomi)

1. **`AllowKey=system.run[*]` in `/etc/zabbix/zabbix_agentd.conf`** su **MARCODG1 e mc2**: l'agent
   Zabbix accetta di **eseguire comandi arbitrari** su richiesta. L'agent ascolta su `0.0.0.0:10050`
   (pubblico); la `Server=` lo limita a Zabbix stesso e a due reti, e `ufw` è **inactive**.
   → chi controlla il server Zabbix, o ne indovina le credenziali, esegue comandi come `zabbix`.
2. **Regola `sudo` verso un file inesistente** su MARCODG1:
   `/etc/sudoers.d/denaro-zabbix` (creato 6 maggio) autorizzava
   `zabbix ALL=(ALL) NOPASSWD: /usr/local/bin/denaro_zabbix.sh` — e **quel file non esiste**.
   Una regola sudo verso un path è una promessa: se il file compare, `zabbix` diventa **root senza
   password**. La catena `system.run` → `zabbix` → `sudo` → root era completa.

Corollari verificati: `zabbix` non ha mai effettuato login (`lastlog`: *Never logged in*), non ha
`.ssh`, e `/usr/local/bin` è scrivibile solo da root. La configurazione dell'agent risulta
modificata a mano (`sudo vi /etc/zabbix/zabbix_agentd.conf` in `~/.bash_history` di marco).

---

## 60.4 Contenimento eseguito (25/09/2026, ~00:12-00:25 CEST)

Ordine applicato: **prima la copia forense, poi la rimozione**.

| # | azione | esito verificato |
|---|---|---|
| 1 | copia forense di binari, crontab, processi e connessioni in `/root/quarantena_miner_20260925/` (root, `chmod go-rwx`) | presente: `binari/`, `crontab_zabbix.txt`, `processi.txt`, `connessioni.txt` |
| 2 | rimozione della persistenza: `crontab -r -u zabbix` + `rm /var/spool/cron/crontabs/zabbix` + restart di cron | `no crontab for zabbix` |
| 3 | terminazione del processo (`SIGTERM`, poi `SIGKILL`) | nessun processo `kworker_sys` |
| 4 | disarmo del binario: `chmod 000` su `.kworker_sys` e `.self` | non più eseguibili |
| 5 | rimozione della regola sudo orfana (backup in quarantena) | `User zabbix is not allowed to run sudo on MARCODG1` |
| 6 | disattivazione di `system.run` (backup dei `.conf`) su **MARCODG1 e mc2** | `AllowKey` attive: **0** su entrambi; agent `active` |
| 7 | verifica | **0 connessioni a porte di pooling**; RAM usata **3114 → 1003 MB** (2,1 GB liberati); nessun indicatore residuo di miner sulle tre macchine |

Nota di metodo: al primo tentativo i tre dump forensi n°1 sono falliti (`Permission denied` su
`/root/...` perché la redirezione avveniva come utente `marco`, non root). Sono stati rifatti sotto
`sudo sh -c` e **verificati presenti**: la quarantena è completa.

---

## 60.5 Cosa resta aperto (richiede il proprietario)

| # | azione | perché è tua |
|---|---|---|
| 1 | **Revocare il PAT GitHub in chiaro** in `/home/marco/.bash_history` (riga 483, `git remote set-url origin https://github_pat_…@github.com/…`). Occorrenze verificate: 1 | il token è tuo; finché è valido, chi ha letto quel file ha accesso ai repo. Va revocato **adesso** e rigenerato |
| 2 | **Ruotare le credenziali Zabbix** (`Admin`/`zabbix` sono hardcoded in `zabbix_healer.sh`, e l'agent accetta `ServerActive` verso un IP interno) | sono credenziali di amministrazione |
| 3 | **Ruotare le chiavi OKX** di tutti i conti: il **vault è interamente morto** (7/7 chiavi rispondono `50119 API key doesn't exist`) e le chiavi vive stanno solo in `config/.env_{nuvola,marcodg1}`, fuori dal vault | la governance delle chiavi è una tua decisione; un file che dichiara chiavi buone e ne contiene di morte è pericoloso |
| 4 | **Decidere sull'host compromesso**: `zabbix` ha girato codice di terzi come utente di servizio su una macchina che custodisce chiavi OKX. Il contenimento ferma il danno, non ripristina la fiducia: la scelta fra *reinstallare* e *convivere con verifiche* è tua | è una decisione di rischio, non tecnica |
| 5 | **Firewall**: `ufw` è `inactive` su MARCODG1, con `10050`, `5432` (postgres), `80/443`, `22` esposti | aprire/chiudere porte è una scelta di esposizione |

---

## 60.6 Le difese strutturali da costruire (le faccio io)

1. **Le unit systemd e i crontab non sono versionati.** È la causa di 10 guasti su 12 (path
   `~/denaro` vs `~/alpha-omega-trading`) **e** della cecità su chi ha toccato cosa. Vanno portati in
   `deploy/systemd/` e `deploy/cron/` con `PROJECT_ROOT` parametrico.
2. **Un controllo di integrità periodico** (nel repo, eseguibile): hash dei binari attesi, presenza
   di `AllowKey` attive, crontab inattesi, processi con nome kernel-like in userspace, connessioni a
   porte di pooling. Deve girare da solo e **urlare** se qualcosa cambia.
3. **Il vault delle chiavi va verificato, non creduto.** `tools/verify_keys.py --read-only` marca le
   chiavi morte; un vault che non si autoverifica produce esattamente l'errore di oggi: la
   telemetria leggeva saldi con chiavi morte e nessuno se ne accorgeva.

---

## 60.7 Lezione per il progetto trading

Il software "zero-touch" deve sorvegliare **anche l'ambiente in cui gira**, non solo gli ordini.
Oggi tre difetti dello stesso tipo sono convissuti per giorni senza un allarme:

- 1.486 tick saltati in silenzio (nodi senza capitale);
- 553+560 restart di servizi morti (path sbagliati);
- 14 ore di CPU di un miner di terzi su una macchina di produzione.

Nessuno dei tre era un errore di strategia. Tutti e tre erano **assenza di un controllo che
dichiara lo stato**. È la stessa correzione in tre punti: uno stato esplicito, una transizione
loggata una volta, un allarme quando cambia.
