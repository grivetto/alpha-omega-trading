# Alpha-Omega Trading — «Denaro»

<p align="center">
  <img src="assets/banner.svg" alt="Alpha-Omega Trading Banner" width="100%"/>
</p>

<h3 align="center">Una flotta di trading algoritmico misurata: tre macchine, strategie complementari, sub-account isolati</h3>

<p align="center">
  <i>Motore di esecuzione multi-nodo indipendente su OKX EEA, con budget di rischio rigidi, telemetria onesta e un gate di promozione che nessuna strategia entra in produzione senza aver passato.</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://www.okx.com/en-eu"><img src="https://img.shields.io/badge/OKX-EEA-000000?style=flat-square" alt="OKX EEA"></a>
  <a href="https://github.com/ccxt/ccxt"><img src="https://img.shields.io/badge/CCXT-4.x-1E88E5?style=flat-square" alt="CCXT"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://www.zabbix.com/"><img src="https://img.shields.io/badge/Zabbix-7.0_LTS-D40000?style=flat-square&logo=zabbix&logoColor=white" alt="Zabbix 7.0 LTS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-CC0_1.0-blue.svg?style=flat-square" alt="CC0 License"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> •
  <a href="README.it.md"><b>Italiano</b></a> •
  <a href="README.es.md"><b>Español</b></a> •
  <a href="README.th.md"><b>ไทย</b></a>
</p>

---

## 📊 Stato in sintesi — 2026-09-25

> **La flotta NON sta facendo trading in questo momento, e non è previsto che lo faccia.** Ogni nodo live
> riporta attualmente `NON FINANZIATO`: i conti exchange dietro le chiavi API live contengono **~0,15 EUR di
> polvere**. Il motore rifiuta di fare trading su un saldo che non può misurare onestamente, e da questa
> release *lo dice* invece di saltare i tick in silenzio. Il finanziamento è una decisione deliberata e separata.

| Area | Stato | Evidenza |
| :--- | :--- | :--- |
| **Ordine del repository** | ✅ riconciliato con `origin`, il lavoro di tutte le sessioni committato | 5 commit pubblicati, `main` allineato |
| **Suite di test** | ✅ **finalmente eseguibile** (prima 63 failed / 50 errors, tutti ambientali) | vedi § Testing |
| **Idempotenza degli ordini** | ✅ implementata (`clOrdId` su ogni invio, journalato *prima* dell'ordine) | 7 test |
| **Stato non finanziato** | ✅ esplicito `ok` / `sottocapitalizzato` / `non_finanziato` / `illeggibile` | 18 test |
| **Limite di esposizione del conto** | ✅ integrato nel nodo (il registro esisteva, nessuno lo aveva costruito) | 15 test |
| **Controllo di integrità della flotta** | ✅ `tools/fleet_integrity.py`, exit code 1 su qualsiasi allarme | 14 allarmi su MARCODG1, 7 su nuvola |
| **Trading live** | ⛔ il saldo del conto è polvere (~0,15 EUR) | journal: 882 + 604 tick saltati |
| **Servizi di telemetria** | ⚠️ 4 unit in riavvio patologico (path drift) | `denaro-watchdog` failed |
| **Sicurezza** | ⚠️ un host è stato compromesso, ora contenuto | vedi § Sicurezza |
| **Economia** | ⚠️ la fascia commissionale attuale annulla l'edge — vedi § L'economia | misurato su commissioni reali |

---

## 🏛 Topologia della flotta

Il sistema gira su tre host, ognuno un **nodo indipendente: una macchina = una famiglia di strategie =
un sub-account OKX**. Non è una scelta stilistica — è la correzione di tre difetti che erano stati
osservati in produzione (vedi § Lezioni).

```
 ┌──────────────────────────────────────────────────────────────┐
 │                  LIVELLO EXCHANGE — OKX EEA                  │
 │      (le chiavi EU funzionano solo contro eea.okx.com)       │
 └───────┬──────────────────┬──────────────────┬────────────────┘
         │                  │                  │
 ┌───────▼────────┐ ┌───────▼────────┐ ┌───────▼──────────────┐
 │ NODO A         │ │ NODO B         │ │ NODO C               │
 │ nuvola         │ │ mc2            │ │ MARCODG1             │
 │ TREND (giorn.) │ │ GRID adattiva  │ │ 4H momentum          │
 │ sub: nuvolasub1│ │ sub: mc2sub1   │ │ sub: marcosub1       │
 │ edge MISURATO  │ │ gate: da       │ │ gate: servono fee    │
 │                │ │ misurare       │ │ sotto 0.30% per lato │
 └────────────────┘ └────────────────┘ └──────────────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ REGIA RISCHIO PORTAFOGLIO  │
              │ un budget: 2% del capitale │
              │ stop −3%/giorno, DD −10%   │
              └────────────────────────────┘
```

**Tre regole non negoziabili:**

1. **Un conto per strategia.** Nessun bot condivide un sub-account con una strategia diversa.
2. **Il rischio è una proprietà del portafoglio, non del singolo bot.** Il budget del 2% è sul capitale
   *totale*. Sette bot che dichiaravano ciascuno l'intero conto rischiavano **il 14% del conto, non il 2%** —
   misurato da `tools/audit_capitale_config.py`.
3. **Nessuna strategia entra in produzione senza passare il gate**: expectancy netta positiva
   out-of-sample, ai costi *reali* del conto su cui gira.

<p align="center">
  <img src="assets/architettura-flotta.svg" alt="Architettura della flotta: tre nodi, un sub-account OKX ciascuno, una regia del rischio di portafoglio" width="100%"/>
</p>

### Tecnologie principali

| Componente | Tecnologia | Funzione |
| :--- | :--- | :--- |
| **Linguaggio / runtime** | Python 3.12+, AsyncIO | event loop del nodo, policy, supervisor |
| **Accesso all'exchange** | CCXT 4.x — OKX EEA REST **e** WebSocket (`ccxt.pro`), hostname **`eea.okx.com`** | dati di mercato e routing degli ordini; le chiavi EU funzionano *solo* contro l'endpoint EEA |
| **Core di esecuzione** | Python, AsyncIO, CCXT | Policy (trend / grid adattiva / mean-reversion), ciclo di vita degli ordini, contabilizzazione dei fill |
| **Core di rischio** | Moduli di dominio puri, nessun I/O | Rischio per operazione, circuit breaker, limite di esposizione del conto, classificazione del finanziamento |
| **Backtest** | Motore proprio, consapevole di commissioni e slippage | Lo stesso codice decisionale del live: un solo rig per entrambi |
| **Operazioni di flotta** | systemd (unit di sistema + utente, `linger`), SSH, Tailscale, Cloudflare Tunnel | Nessuna esposizione in ingresso; telemetria solo su loopback |
| **Telemetria** | Zabbix 7.0 LTS (un agent per host), Prometheus, Grafana, endpoint di health | Curve di equity, salute dei tick, badge di obsolescenza |
| **Integrità** | `tools/fleet_integrity.py` | Controlli su miner / crontab / sudoers / path delle unit / porte, con exit code |
| **Packaging** | Docker + `docker-compose`, `venv`, `requirements.txt` | Ambienti riproducibili su tre host |
| **Qualità** | pytest (**382 passed, 3 skipped**), ruff | Una suite eseguibile è la precondizione per verificare qualsiasi cosa |
| **CI** | GitHub Actions | lint e test a ogni push |
| **Configurazione e segreti** | Config di nodo YAML, un `.env_<node>` per nodo (mode 600, in gitignore) | Un conto per nodo, isolato tramite `env_prefix` |
| **Controllo di versione** | git, un solo writer per path | Provenienza: chi ha cambiato cosa, e quando |

---

## 🧪 Testing — e perché è stata la correzione più grande di questo ciclo

```bash
python -m pytest denaro/tests -q      # 382 passed, 3 skipped
```

Per settimane la suite ha riportato **63 failed e 50 errors**. Quasi nessuno di essi era un difetto di
codice: erano **errori di permessi dell'ambiente**. La causa radice, isolata con tre sonde dirette:

```
os.makedirs(<repo>/.pytmp/probe) + write   -> OK
tempfile.mkdtemp()               + write   -> PermissionError
os.makedirs(...) + open(...)     -> OK
```

`tempfile.mkdtemp` viene rifiutato mentre `os.makedirs` funziona — e sia `TemporaryDirectory` sia
`tmp_path` di pytest passano da lì. La conseguenza era il danno vero: **due sessioni di lavoro
indipendenti non potevano verificare nulla**, e una suite il cui risultato è rumore non può proteggere
nulla. `denaro/tests/conftest.py` ora lo sostituisce alla radice: il risultato è passato da *63 failed /
50 errors* a **1 fallimento reale**, che è un gap semantico noto (vedi § Lavoro aperto).

---

## 💰 L'economia — detta senza giri di parole

Il numero decisivo non è la strategia, è il pedaggio. Misurato dalle pagine ufficiali delle commissioni di OKX EEA:

| conto | maker | taker | round trip | edge lordo di break-even per operazione |
| :--- | :--- | :--- | :--- | :--- |
| OKX EEA **senza** derivati (oggi) | 0,200% | **0,350%** | **0,700%** | **0,70%** |
| OKX EEA **con** X-Perps aperti | 0,080% | **0,100%** | **0,200%** | 0,20% |

Aprire un conto derivati su OKX EEA **non** richiede volume né capitale — solo KYC più una
*valutazione di appropriatezza*. Sposta il conto dalla tabella dello 0,35% a quella dello 0,10%.

**E una correzione che circolava da giorni:** il `−1,97%` del trend daily è un **alpha cumulato su 2,4
anni**, non un rendimento giornaliero. A costo zero il segnale è significativo (t = +4,51); a 0,35% per
lato è **indistinguibile da zero** (t = −0,30). Non è una strategia che sanguina — è una strategia che il
pedaggio cancella.

Le due leve che moltiplicano davvero:

- **abbassare il pedaggio** — da 0,70% a 0,20% per round trip, il che moltiplica per 3,5× la frequenza sostenibile;
- **alzare la frequenza** — la famiglia 4H passa da 3/24 a 18/24 configurazioni robuste alla stessa
  commissione più bassa, cioè ~8× le opportunità.

Nessuna delle due è codice. Una è una valutazione; l'altra è la sua conseguenza.

---

## 🛡 Gestione del rischio

- **Rischio per operazione** — 2% del capitale, fissato in configurazione e pubblicato nell'health.
- **Circuit breaker** — stop giornaliero a −3%, drawdown massimo a −10%, persistiti attraverso i riavvii.
- **Limite di esposizione del conto** — la *somma* di tutti i bot sullo stesso sub-account, non per bot.
- **Classificazione del finanziamento** — un nodo senza capitale dichiara `NON FINANZIATO` una volta per
  transizione, non piazza ordini e non inquina mai le baseline di picco / giornaliere / settimanali. Esce
  dallo stato da solo quando arrivano i fondi, senza un riavvio.
- **Idempotenza degli ordini** — ogni invio porta un `clOrdId`, journalato *prima* che l'ordine parta; un
  ordine che sopravvive a un crash viene riconosciuto come nostro al riavvio invece di essere contato come
  sconosciuto.
- **Semantica dello stop** — lo stop vende la quota del bot stesso (`tracked size + bought-not-resold`),
  mai il saldo libero del conto: con due bot su un sub-account, il vecchio comportamento liquidava
  l'inventario di un altro bot.
- **Supervisor** — la pressione su RAM/CPU limita gli intervalli dei tick (`nominal` → `caution` → `safe` →
  `emergency`).

---

## 🔒 Sicurezza — un host è stato compromesso, ora contenuto (2026-09-25)

Un audit della flotta ha trovato un **cryptominer di terze parti** su MARCODG1: un binario ELF in
`/var/tmp/.X11-unix-socket/`, in esecuzione come utente di servizio `zabbix` per **4 giorni**, 199% di CPU
e 2,1 GB di RAM, con persistenza via cron e una connessione attiva a un mining pool. È stata la causa
diretta dell'oscillazione `SafeMode safe ↔ caution` del nodo live (RAM all'87%).

Contenimento, con copie forensi fatte **prima** di qualsiasi cancellazione:

| azione | esito verificato |
| :--- | :--- |
| processo terminato | nessun PID, 0 connessioni al pool |
| RAM | utilizzata **3114 → 1003 MB** |
| persistenza cron | rimossa (spool verificato su disco) |
| binario | `chmod 000` + copia in `/root/quarantena_miner_20260925/` |
| regola `sudo` orfana per `zabbix` | rimossa → *not allowed to run sudo* |
| `AllowKey=system.run[*]` | disabilitato su **entrambi** gli host |

**Aperto per il proprietario:** revocare il PAT GitHub trovato in chiaro nella history di una shell;
ruotare le credenziali Zabbix; decidere se ricostruire l'host compromesso; rigenerare il key vault (7
chiavi OKX su 7 sono morte); rivedere il firewall (`ufw` inattivo, `5432` e `10050` esposte).

---

## 📚 Lezioni («La Baracca»)

Il progetto era stato soprannominato in origine *«La Baracca»* — italiano per un aggeggio improvvisato che
ha sempre bisogno di un'altra toppa. Il nome è invecchiato bene. Cosa hanno insegnato i mercati live, in
ordine di costo:

1. **Il capitale frammentato va in stallo.** Saldi piccoli sparsi su molti sub-account, ognuno con ordini
   aperti, riducono a zero il saldo libero.
2. **Il pedaggio non è un dettaglio.** Commissioni e slippage cancellano in silenzio edge che i backtest
   mostrano comodamente.
3. **Ogni bot che dichiara l'intero conto moltiplica il rischio per N.** Sette bot × 2% = 14%.
4. **Una guardia senza stato è un fallimento silenzioso.** 1.486 tick saltati sono sembrati «non è
   successo nulla» per ore, perché nessuno stato diceva «non sono finanziato».
5. **Gli ordini non tracciati dopo un crash sono denaro invisibile.** Da qui le chiavi di idempotenza.
6. **Una telemetria che si legge come un fossile è peggio di nessuna telemetria.** I file di health
   obsoleti contano come «running» a meno che qualcosa non ne controlli esplicitamente l'età.
7. **Il path drift in produzione rompe tutto insieme.** Dieci delle dodici unit rotte condividevano una
   sola causa radice: un percorso di progetto obsoleto nelle unit systemd e nei crontab che non sono mai
   stati versionati.

---

## 🛠 Avvio rapido

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # le credenziali restano in locale: mai committare segreti

# controllo di integrità della macchina (read-only, exit code 1 su allarme)
python tools/fleet_integrity.py
python tools/fleet_integrity.py --host nuvola --host MARCODG1 --host mc2

# test
python -m pytest denaro/tests -q

# un nodo
python -m denaro.denaro_node --config config/node_nuvola_trade.yaml

# backtest onesto contro commissioni reali
python -m denaro.backtest --config config/node_nuvola_trade.yaml --days 60 --fee 0.0035
```

---

## 🚧 Lavoro aperto, in ordine di valore

1. **Registrare la posizione del grid al fill.** L'unico fallimento reale di test rimasto: un grid compra,
   il fill non viene registrato come posizione aperta, e lo stop ripiega nel dedurlo dagli ordini di
   vendita. Corretto, ma non sufficiente.
2. **Isolamento dei test.** Un test passa da solo e fallisce nella suite → stato condiviso tra i test.
   Collegato: `pytest-asyncio` non è installato e `asyncio_mode` è un'opzione sconosciuta, quindi i test
   async attualmente girano attraverso un meccanismo inspiegato.
3. **Telemetria** — 4 unit in riavvio patologico, tutte dal path drift `~/denaro` vs `~/alpha-omega-trading`.
4. **Versionare l'infrastruttura** (`deploy/systemd/`, `deploy/cron/` con un `PROJECT_ROOT`
   parametrizzato): la causa radice di 10 delle 12 unit rotte, e della cecità su chi ha cambiato cosa.
5. **Capitale.** La variabile decisiva, e deliberatamente separata dal codice.

## 🗺 Percorso di scalabilità

La struttura è identica a ogni scala: **un nodo = una strategia = un conto**. Quello che cambia è il
*numero di nodi*, non il numero di strategie stipate su un conto. Stiparle insieme è l'esperimento già
fatto — e ha prodotto il 14% di rischio aggregato, bot che si fermano a vicenda sull'equity condiviso, e
uno stop che liquidava l'inventario di un altro bot.

- [x] **Ora:** repository in ordine, tre difetti critici chiusi con prove, controllo di integrità
      operativo, suite eseguibile.
- [ ] **Poi:** registrazione del fill del grid, isolamento dei test, telemetria riparata, infrastruttura versionata.
- [ ] **Successivamente:** il gate sulle commissioni — portare **un** conto in uno stato pulito e richiedere
      l'upgrade ai derivati. Non tocca alcun deployment, è reversibile, ed è l'unica azione che sblocca
      la frequenza.
- [ ] **Successivamente:** capitale a stadi, e solo su evidenza out-of-sample.

---

## ⚖️ Disclaimer

**Questo software è distribuito esclusivamente per scopi didattici, accademici e di ricerca. Non
costituisce consulenza finanziaria né di investimento.** Il trading algoritmico su criptovalute comporta
un rischio finanziario sostanziale, inclusa la possibile perdita di tutto il capitale investito. Gli
autori non rilasciano alcuna dichiarazione o garanzia riguardo alla redditività o alle prestazioni del
sistema. Non fare mai trading con capitale che non puoi permetterti di perdere.

---

## 📄 Licenza

Dedicato al pubblico dominio sotto Creative Commons Zero (CC0 1.0 Universal). Vedi [LICENSE](LICENSE).
