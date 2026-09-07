# Alpha-Omega Trading

**_Nome in codice "Denaro" — un motore di trading a griglia unificato e distribuito per OKX e Kraken, con paper trading realistico, capitale live a scaglioni e monitoraggio Zabbix._**

Alpha-Omega Trading è un sistema Python che esegue lo stesso motore di trading su più macchine ("nodi"), ciascuna attiva su uno o più mercati OKX o Kraken tramite la libreria CCXT. È progettato per un deployment disciplinato, validato prima con backtest e paper trading, con un **budget live piccolo e a scaglioni** — il conto live è tenuto volutamente separato dallo sviluppo ed è abbastanza piccolo da rendere sostenibile un eventuale drawdown completo mentre il motore è ancora in fase di validazione.

> [English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · [ไทย](README.th.md)

---

## Indice

- [Stato onesto](#stato-onesto)
- [Cosa fa](#cosa-fa)
- [Architettura](#architettura)
- [Controlli di rischio e sicurezza](#controlli-di-rischio-e-sicurezza)
- [Monitoraggio e alerting](#monitoraggio-e-alerting)
- [Per iniziare](#per-iniziare)
- [Eseguire nodi live e paper](#eseguire-nodi-live-e-paper)
- [Eseguire come servizi systemd](#eseguire-come-servizi-systemd)
- [Configurazione](#configurazione)
- [Struttura del repository](#struttura-del-repository)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)
- [Licenza](#licenza)

---

## Stato onesto

Questo è **software di livello ricerca in validazione live**, non un prodotto finito che fa soldi.

- Il trading è reale ma condotto con un **budget di capitale piccolo** (dell'ordine di decine di euro), volutamente limitato perché bug e drawdown siano sostenibili mentre il motore viene messo alla prova.
- Le strategie vengono prima validate in un **motore di paper trading realistico**, prima di impegnare qualsiasi capitale live, e il capitale live andrebbe aumentato **per scaglioni** solo al superamento di soglie statistiche definite (vedi [Roadmap](#roadmap)).
- I tentativi passati **non hanno prodotto risultati forti e costanti**. Il codice attuale incorpora le lezioni di quei tentativi: enfasi su kill-switch, stop-loss, controlli pre-flight e contabilità onesta di fee e slippage, piuttosto che su previsioni ottimistiche.
- Nessuna cifra in questo repository è una promessa di rendimenti futuri. Vedi il [Disclaimer](#disclaimer).

Tratta questo repository come riferimento su come (non) si opera una piccola flotta di trading algoritmico, e gestisci le tue aspettative di conseguenza.

---

## Cosa fa

Il motore esegue **grid trading bilaterale**: piazza ordini di acquisto quando il prezzo scende entro una scala di livelli configurata, e ordini di vendita ai livelli di take-profit sopra, raccogliendo piccoli guadagni dalle oscillazioni mentre mantiene inventario tra i livelli. Sotto `denaro/domain/` vivono diverse famiglie di strategia (grid, momentum, mean-reversion, adaptive/volatility e varianti basate sul regime di mercato); il motore nodo attorno a esse è condiviso e indipendente dall'exchange.

Caratteristiche principali:

- **Motore unificato, molti mercati.** Lo stesso processo `denaro.denaro_node`, guidato da un file YAML, esegue qualsiasi combinazione di mercati live e paper con capitale, simboli, livelli e impostazioni di rischio per bot.
- **Paper trading realistico.** Un motore paper dedicato applica fee reali dell'exchange, notional minimo, slippage e stop-loss, così i risultati della simulazione sono confrontabili con il comportamento live.
- **Indipendente dall'exchange.** Tutto l'accesso a ordini e dati di mercato sta dietro un layer di adattatori (basati su CCXT) in `denaro/infrastructure/exchanges`, quindi le strategie non parlano mai direttamente con un exchange specifico.
- **Orientato alle prestazioni.** I/O asincrono, feed di prezzi WebSocket con fan-out ZMQ, rate limiting e un supervisor che limita i tick sotto pressione di CPU/RAM.

---

## Architettura

La flotta è distribuita su tre classi di macchina **per ruolo**, non per una topologia fissa:

- **Nodi di trading** — host VPS (il progetto oggi ne usa due) che eseguono uno o più processi `denaro_node`. Ciascuno interpreta il proprio `config/node_*.yaml` e riporta lo stato di salute.
- **Host di monitoraggio** — una macchina che aggrega la salute dei nodi ed esegue il monitoraggio. In questa installazione sta dietro CGNAT e viene raggiunta solo tramite **tunnel SSH inversi** originati dai nodi di trading, quindi non serve alcuna regola firewall in ingresso.
- **Livelli opzionali di orchestrazione / feeder** — il motore include anche un layer "brain"/feeder usato per coordinare decisioni di livello superiore e scambiare segnali tra componenti.

Una vista semplificata delle relazioni a runtime:

```
┌──────────────┐   ┌──────────────┐     ┌──────────────┐
│   NODO A     │   │   NODO B     │     │ ORCHESTRATORE│
│ denaro_node  │   │ denaro_node  │     │ (opzionale)  │
│ mercati grid │   │ mercati grid │     │  brain/feed  │
└──────┬───────┘   └──────┬───────┘     └──────┬───────┘
       │                  │                    │
       └─────────┬────────┴────────────────────┘
                 │   health / metriche via rete
        ┌────────▼─────────┐
        │  MONITORAGGIO    │   Server Zabbix + dashboard web
        │ (aggrega, accesso│   raggiungibile via tunnel SSH inverso
        │   https)         │
        └──────────────────┘
```

Comunicazione, piano di controllo e dettagli di monitoraggio dipendono dal deployment; il meccanismo attualmente usato sono **tunnel SSH inversi (autossh)** così che anche un host dietro NAT possa essere raggiunto e fungere da server di monitoraggio.

---

## Controlli di rischio e sicurezza

La gestione del rischio è un requisito di primo livello, integrato nel motore del nodo e non aggiunto botta-e-risposta a ogni strategia:

- **Stop-loss** per bot e un **circuit-breaker giornaliero/settimanale** che ferma un simbolo o un nodo quando vengono superati i limiti di perdita configurati.
- **Controlli pre-flight** prima di piazzare ogni ordine (validazione anti-deadlock e dimensionamento della posizione) così un bot malconfigurato o bloccato non possa fare trading alla cieca.
- **Safe mode** — un insieme di stati di throttling progressivo (caution → safe → emergency) guidato dal supervisor (pressione RAM/CPU/tick) che rallenta o ferma gradualmente un nodo prima che le risorse si esauriscano.
- **Sub-account.** Il trading live OKX/Kraken gira su **sub-account** dedicati dell'exchange, mai sul conto principale, così eventuali errori operativi restano contenuti.
- **Credenziali** presenti solo in un `.env` locale (mai committato) e caricate a runtime.
- **Budget live a scaglioni.** Il capitale cresce per fasi esplicite (paper → live piccolo → live più ampio) e solo dopo il superamento dei trigger registrati in roadmap.

---

## Monitoraggio e alerting

- **Zabbix** è il backend di aggregazione e alerting. I nodi inviano metriche (equity, PnL per bot, blocchi pre-flight, health scaduta, pressione risorse) al **trapper** di Zabbix.
- Esistono trigger per: superamento circuit-breaker, perdita giornaliera/settimanale, heartbeat scaduti, blocchi pre-flight, pressione risorse.
- **L'auto-heal è disabilitato di default.** Le prime iterazioni riavviavano bot live in modo spurio; il ripristino è ora un'azione deliberata e loggata, non un restart automatico.
- Una **dashboard web** in sola lettura fornisce una vista immediata della salute di nodi e bot.

---

## Per iniziare

Requisiti:

- Python **3.12+**
- Un ambiente `uv` o `venv`
- Docker + Docker Compose solo se esegui anche lo stack di monitoraggio Zabbix
- Chiavi API dell'exchange per OKX e/o Kraken (in un `.env` locale, mai committate)

Clona e installa:

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # poi inserisci le tue chiavi API
```

---

## Eseguire nodi live e paper

Il motore è un'applicazione console guidata da un file di configurazione:

```bash
# Nodo grid live (in base al file di config)
python -m denaro.denaro_node --config config/node.yaml

# Nodo paper trading
python -m denaro.denaro_node --config config/node_paper.yaml

# Config live trend-following su Kraken (esempio)
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml
```

Altri file forniti (`config/node_nuvola.yaml`, `config/node_mc2.yaml`, `config/node_adaptive_vol_grid_paper.yaml`, …) corrispondono a ruoli nodo/strategia specifici; vedi la sezione [Configurazione](#configurazione).

Esegui `python -m denaro.denaro_node --help` per le opzioni (è supportato `--verbose`).

---

## Eseguire come servizi systemd

Per i nodi di produzione i file unit sono forniti in `systemd/`. Passi tipici su un dato host:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now denaro-node            # il nome dipende dal ruolo dell'host
```

Le unit attuali coprono i ruoli node, health, aggregator, dashboard, feeder e tunnel inverso (`zabbix-tunnel`). **Regola i path `ExecStart`** nelle unit per corrispondere a home utente, path del repository e venv del singolo host — i valori distribuiti riflettono una specifica installazione.

---

## Configurazione

Ogni nodo legge un file YAML che definisce, tra le altre cose:

- `exchange_rest`: exchange (es. `okx`) e modalità EEA.
- `bots`: una lista di mercati, ciascuno con simbolo, `mode` (`live`/`paper`), `capital`, `levels` della griglia e impostazioni strategia-specifiche.
- `safemode`: le soglie di throttle RAM/CPU (`caution_pct`, `safe_pct`, `emergency_pct`) e il relativo intervallo.
- `supervisor`: soglie critiche delle risorse e throttling dei tick.
- `data_dir`: dove il nodo salva stato a runtime e dati di mercato.

Tieni le credenziali exchange fuori dai file di config — mettile in `.env` e caricale a runtime.

---

## Struttura del repository

```
config/                  Configurazione YAML per nodo
denaro/
  domain/                Logica strategie e rischio/regime/indicatori (grid, momentum, adaptive, …)
  application/           Orchestrazione: portfolio, supervisor, safe-mode
  infrastructure/        Adattatori exchange (CCXT), market data, storage, feeder
  denaro_node.py         Entry point unificato del nodo
scripts/                 Helper di deployment
systemd/                 File unit systemd (node, health, aggregator, tunnel, …)
zabbix/                  Integrazione monitoraggio (healer, push_metrics)
tests/                   Test
.env.example             Template credenziali (le chiavi non vengono mai committate)
```

---

## Testing

Il progetto usa `pytest` (con `pytest-asyncio` per i layer asincroni). Installa gli extras dev ed esegui:

```bash
pip install -e ".[dev]"
pytest
```

---

## Roadmap

- [ ] Sostenere un record live validato su una finestra di osservazione definita (es. diverse settimane per bot).
- [ ] Soglie di promozione automatiche: una strategia riceve più capitale solo se supera le soglie registrate (profit factor, max drawdown, Sharpe).
- [ ] Aumento del capitale a scaglioni (paper → live piccolo → 100–500 EUR → 1000 EUR) al raggiungimento delle condizioni.
- [ ] Template di monitoraggio con grafici equity/PnL/volume per bot.
- [ ] Packaging pulito: allineare i metadati di `pyproject.toml` alla struttura reale del pacchetto `denaro`.

---

## Disclaimer

**Questo software è fornito solo per scopi educativi e di ricerca. Non è consulenza finanziaria.** Il trading algoritmico di asset crypto comporta un rischio sostanziale, inclusa la perdita totale del capitale impiegato. Le performance passate o di paper trading non garantiscono risultati futuri; fee, slippage, vuoti di liquidità e interruzioni dell'exchange possono trasformare un backtest redditizio in una campagna live in perdita. Impiega solo capitale che puoi permetterti di perdere per intero, e mai denaro di cui dipendi. Gli autori non si assumono alcuna responsabilità per perdite derivanti dall'uso di questo codice.

---

## Licenza

Pubblico dominio (equivalente CC0). Vedi il file [LICENSE](LICENSE) per la dedica completa — senza diritti riservati; usalo, copialo, modificalo e vendilo liberamente, a tuo rischio.
