# Alpha-Omega Trading

**_Nome in codice "Denaro" — Sistema di trading algoritmico distribuito e motore di esecuzione multi-nodo per OKX e Kraken._**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Zabbix](https://img.shields.io/badge/Zabbix-D40000?style=for-the-badge&logo=zabbix&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white)
![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)

Alpha-Omega Trading è una piattaforma di esecuzione multi-host che opera su una topologia distribuita di server (`nuvola`, `MARCODG1` e `mc2`). Gestisce strategie automatizzate di grid trading, momentum e modelli adattivi di regime sugli exchange crypto tramite CCXT, vincolata da telemetria real-time e gate di supervisione del rischio.

> [English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · [ไทย](README.th.md)

---

## Architettura e Stack Tecnologico

```
 ┌─────────────────────────────────────────────────────────┐
 │                   EXCHANGES LAYER                       │
 │              OKX (EEA)   ·   Kraken REST/WS             │
 └─────────────┬───────────────────────────┬───────────────┘
               │ Esecuzione CCXT           │ Esecuzione CCXT
 ┌─────────────▼─────────────┐ ┌───────────▼───────────────┐
 │       NODO: mc2           │ │      NODO: MARCODG1       │
 │   (Home Node / CGNAT)     │ │        (Cloud VPS)        │
 │ · denaro-node-mc2         │ │ · denaro-node-trend-live  │
 │ · Docker Zabbix Server    │ │ · Zabbix Push Metrics     │
 │ · Dashboard Web (:8913)   │ │ · Aggregator API (:8912)  │
 └─────────────┬─────────────┘ └───────────┬───────────────┘
               │                           │
               └─────────────►◄────────────┘
                 Tunnel SSH Inversi (autossh)
                 Zabbix Trapper :10051 / Reverse 2222
```

- **Runtime & Core Engine:** Python 3.12+, AsyncIO, CCXT Pro per la connettività diretta con gli exchange.
- **Topologia & Comunicazione:** 3 nodi attivi interconnessi tramite tunnel SSH inversi (`autossh`) e tunnel Cloudflare per superare ambienti con CGNAT in sicurezza.
- **Monitoraggio & Osservabilità:** Stack Zabbix 7.0 LTS containerizzato in Docker su mc2, alimentato da invii ad alta frequenza tramite Zabbix Trapper.
- **Dashboard & Telemetria:** Servizio HTTP/JSON asincrono dedicato con dashboard visuale su `web.grivetto.eu`.

---

## Storia e Lezioni Apprese ("La Baracca")

Il progetto è nato come framework di esplorazione algoritmica soprannominato *"La Baracca"* — termine colloquiale che esprime la natura imperfetta di un sistema in continua evoluzione e riparazione, lontano da illusioni di facili guadagni.

### La realtà del trading algoritmico
Nelle fasi iniziali di sviluppo, test su modelli ingenui, overfitting nei backtest e disconnessioni API hanno chiarito che il codice deve fare i conti con la dura realtà dei mercati reali:
- **Commissioni e Slippage:** Le fee maker/taker erodono rapidamente margini stretti di griglia.
- **Limiti API e Requisiti Normativi:** Gli endpoint conformi EEA richiedono riconnessioni resilienti e stringente gestione dei rate limit.
- **Rischio di Mercato:** Le griglie statiche non protette durante trend ribassisti portano rapidamente al blocco del capitale.

Per questi motivi l'architettura è stata riscritta con solide basi ingegneristiche: stop-loss obbligatori, verifiche pre-flight anti-deadlock, safe-mode con throttle su CPU/RAM e gestione isolata dei sub-account.

---

## Work in Progress Attivo (Fase Live: 25 + 25 EUR)

Operiamo su una rigorosa roadmap a scaglioni di capitale. Il trading live è attualmente limitato a un envelope di prova (~50 EUR totali) per verificare robustezza e tenuta dei bot:

| Exchange | Coppia | Modalità | Capitale Assegnato | Strategia | Host Nodo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kraken** | `SOL/EUR` | **Live** | ~12.70 € | Momentum | `MARCODG1` |
| **Kraken** | `XRP/EUR` | **Live** | ~12.70 € | Momentum | `MARCODG1` |
| **OKX** | `DOGE/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) |
| **OKX** | `SOL/EUR` | **Live** | ~12.00 € | Multi-level Grid | `mc2` (`mc2sub1`) |

### Priorità di Sviluppo in Corso:
1. **Finestra di Osservazione Live:** Monitoraggio continuo di riempimenti, slippage e fee su un orizzonte di più settimane per i 4 bot attivi.
2. **Spaziatura Dinamica e Volatilità:** Perfezionamento dell'adattamento delle griglie in funzione della volatilità (ATR).
3. **Passaggio di Scaglione (Staging):** Incremento del capitale da ~50 EUR a 100 EUR, 500 EUR e successivamente fino a 1.000 EUR solo al superamento comprovato dei target statistici di Sharpe Ratio e Profit Factor.

---

## Controlli di Sicurezza e Rischio

- **Validazione Pre-Flight:** Controlli anti-deadlock verificano saldo libero ed equity prima di inviare ogni singolo ordine.
- **Supervisor Safe Mode:** Monitoraggio in tempo reale di RAM, CPU e lag dei tick. Rallenta o arresta l'engine se le risorse superano le soglie di sicurezza.
- **Isolamento Sub-Account:** L'esecuzione live avviene solo su sub-account dedicati (`TRENDSUB` su Kraken, `mc2sub1` su OKX).
- **Zero Credenziali nel Repository:** Tutte le chiavi risiedono nei file `.env` locali esclusi da Git.

---

## Avvio Rapido

```bash
# Clona il repository
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading

# Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Configura ambiente
cp .env.example .env
```

```bash
# Avvia un nodo con configurazione
python -m denaro.denaro_node --config config/node_trend_live_kraken.yaml

# Esegui i test
pytest
```

---

## Disclaimer

**Questo software è fornito esclusivamente a scopo didattico, accademico e di ricerca. Non costituisce consulenza finanziaria.** Il trading su criptovalute comporta elevati rischi di perdita totale del capitale. Gli autori non si assumono alcuna responsabilità per perdite finanziarie derivanti dall'uso di questo codice. Non impiegare mai denaro che non ci si possa permettere di perdere.

---

## Licenza

Rilasciato nel pubblico dominio tramite Creative Commons Zero (CC0). Consulta il file [LICENSE](LICENSE) per tutti i dettagli.
