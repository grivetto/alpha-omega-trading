# Progetto Denaro

> Sistema di grid trading autonomo su Binance. Multi-macchina, multi-pair, capitale consolidato.  
> **Versione attuale:** v3.0.0 | **Data:** 24 Giugno 2026  
> **Fase:** Produzione (post-audit e refactoring)

---

## 🎯 Obiettivo

Generare profitto costante con grid trading automatizzato su Binance spot, minimizzando le commissioni, ottimizzando le chiamate API, e proteggendo il capitale con circuit breaker integrato.

Dopo 6 mesi di sperimentazione (v1/v2) con strategie multiple (grid, arbitrage, scalping, LLM optimizer, Squadra multi-bot), il progetto è stato ridotto all'essenziale: **solo grid trading su 3 pair decorrelati**.

---

## 🏗️ Architettura v3

```
┌──────────────────────────────────────────────────┐
│                  Binance Spot                     │
│                                                   │
│  mc2orion (SOL)  nuvolatrading (DOGE)  marcodg1  │
│  ~$200 USDC       ~$0 (da trasferire)  ~$0 + ADA │
└──────┬────────────────┬────────────────┬─────────┘
       │                │                │
  ┌────▼─────┐    ┌────▼─────┐    ┌────▼─────┐
  │ MC2      │    │ Nuvola   │    │ MARCODG1 │
  │ Torino   │    │ IONOS    │    │ IONOS    │
  │ 15GB RAM │    │ 3.8GB    │    │ 3.8GB    │
  │          │    │          │    │          │
  │ SOL/USDC │    │ DOGE/USDC│    │ ADA/USDC │
  └──────────┘    └──────────┘    └──────────┘
```

### Componenti

| Componente | File | Descrizione |
|-----------|------|-------------|
| **DataFeeder** | `data_feeder.py` | Cache API con TTL. Una fetch = N consumers. -90% API calls |
| **CircuitBreaker** | `circuit_breaker.py` | Protezione capitale pre-trade. 3 stati: CLOSED/HALF_OPEN/OPEN |
| **GridEngine** | `grid_engine.py` | Grid trading puro: livelli, ordini, rilevamento fill, P&L |
| **LeaderElection** | `leader_election.py` | Failover: una sola istanza per pair condiviso |
| **Main** | `main.py` | Loop principale. Multi-pair, multi-machine |
| **Config** | `config.py` | Dataclass tipizzate: Grid, Risk, API |

### Servizi systemd

| Macchina | Servizio | Pair | Capitale |
|----------|----------|------|----------|
| MC2 | `denaro-v3` | SOL/USDC | ~$200 USDC |
| Nuvola | `denaro-v3` | DOGE/USDC | ~$0 (da trasferire) |
| MARCODG1 | `denaro-v3` | ADA/USDC | ~$0 (da trasferire) |

### Monitoring

| Strumento | URL / Accesso | Cosa monitora |
|-----------|---------------|---------------|
| **Zabbix** | `http://mc2:1080` (Admin/zabbix) | 14 item, 4 trigger, trend 365gg |
| **Log** | `tail -f ~/denaro/denaro_v3.log` | Cicli grid, fill, P&L, errori |

---

## 📁 Struttura del repository

```
alpha-omega-trading/
├── denaro_v3/              # Motore v3 (attivo)
│   ├── main.py             # Loop principale
│   ├── config.py           # Configurazione
│   ├── data_feeder.py      # Cache API
│   ├── circuit_breaker.py  # Risk management
│   ├── grid_engine.py      # Grid trading
│   ├── leader_election.py  # Failover
│   └── denaro-v3.service   # Systemd unit
├── core/                   # Moduli legacy (risk, kill_switch)
├── strategies/             # Vecchie strategie (archiviate)
├── squadra/                # Squadra v5 (FERMA)
├── config/                 # Config centralizzata v2
├── tests/                  # Unit test (circuit breaker, data feeder)
├── ARCHITECTURE_V3.md      # Documento di architettura
├── Progetto Denaro.md      # Questo file
├── .keys.json              # API keys (NON COMMITTARE)
├── .env.example            # Template .env
└── requirements.txt        # Dipendenze Python
```

---

## 🔑 Sub-account Binance

| Sub-account | Macchina | Pair | Capitale | Stato chiave |
|-------------|----------|------|----------|--------------|
| `mc2orion_virtual@...` | MC2 | SOL/USDC | ~$200 | ✅ Attiva |
| `nuvolatrading_virtual@...` | Nuvola | DOGE/USDC | $0 | ⚠️ Da verificare |
| `marcodg1marcosol_virtual@...` | MARCODG1 | ADA/USDC | $0 + 0.03 ADA | ✅ Attiva |
| `sergio@grivetto.eu` | — | Deposito | ~0.00064 BTC | 🔒 No trading |

Tutte le chiavi salvate in `.keys.json` (gitignorato).

---

## 🐛 Lezioni apprese (6 mesi di errori)

1. **Capitale frammentato = deadlock** — $200 divisi su 3 account con grid bot separati bloccano la liquidità. Ogni ordine open riduce il free balance a zero. **Fix v3:** capitale consolidato, grid engine calcola amount corretto per buy e sell.

2. **CCXT precision bug** — ccxt 4.x restituisce `precision.amount = 0.001` (float) invece che `3` (int). `int(0.001) = 0` → `round(x, 0) = 0.0` → amount = 0.001 (minimo). **Fix v3:** `math.floor(amount / step_size) * step_size` quando step_size < 1.

3. **Circuit breaker falso positivo** — `get_total_balance("USDC")` non include il valore degli ordini aperti. Dopo aver piazzato BUY, l'equity scende del valore locked → drawdown falso. **Fix:** calcolare equity come USDC total + valore market di tutti gli asset.

4. **API calls senza ROI** — 10 servizi indipendenti fetchavano OHLCV/balance/ticker separatamente. LLM optimizer sempre `hold`, Squadra WR=5%. **Fix v3:** DataFeeder centralizzato con cache TTL, singolo processo per macchina.

5. **Servizi fantasma** — `denaro-flash-crash` (4656 restart), `ollama.service` (21853), `pattern-pro` — file mancanti ma systemd in restart loop infinito. **Fix:** kill + mask + rimozione unit file.

6. **`.env` pulizia** — 18 file `.env.bak.*` accumulati in 3 mesi. Ogni key rotation creava backup. **Fix:** tenere max 2 backup, il resto va eliminato.

---

## 🔄 Deploy workflow

```bash
# 1. Sviluppo locale
cd C:\dev\alpha-omega-trading

# 2. Deploy su tutte le macchine
scp denaro_v3/*.py sergio@mc2:/home/sergio/denaro/denaro_v3/
scp denaro_v3/*.py sergio@nuvola:/home/sergio/denaro/denaro_v3/
scp denaro_v3/*.py marco@MARCODG1:/home/marco/denaro/denaro_v3/

# 3. Riavvio
ssh sergio@mc2 'sudo systemctl restart denaro-v3'
ssh sergio@nuvola 'sudo systemctl restart denaro-v3'
ssh marco@MARCODG1 'sudo systemctl restart denaro-v3'

# 4. Verifica
ssh sergio@mc2 'tail -5 ~/denaro/denaro_v3.log'
```

---

## 📋 Comandi rapidi

```bash
# Saldi
ssh sergio@mc2 'cd ~/denaro && export $(grep -v "^#" .env | xargs) && ./venv/bin/python3 -c "
import ccxt,os;e=ccxt.binance({\"apiKey\":os.environ[\"BINANCE_API_KEY\"],\"secret\":os.environ[\"BINANCE_API_SECRET\"]})
b=e.fetch_balance()
for a,v in b.items():
    if isinstance(v,dict) and v.get(\"total\",0)>0: print(f\"{a}: {v[\"total\"]}\")
"'

# Ordini aperti
ssh sergio@mc2 'cd ~/denaro && export $(grep -v "^#" .env | xargs) && ./venv/bin/python3 -c "
import ccxt,os;e=ccxt.binance({\"apiKey\":os.environ[\"BINANCE_API_KEY\"],\"secret\":os.environ[\"BINANCE_API_SECRET\"]})
for sym in [\"SOL/USDC\",\"DOGE/USDC\",\"ADA/USDC\"]:
    for o in e.fetch_open_orders(sym): print(f\"{sym}: {o[\"side\"]} {o[\"amount\"]} @ {o[\"price\"]}\")
"'

# Stato servizi
ssh sergio@mc2 'systemctl is-active denaro-v3'
ssh sergio@nuvola 'systemctl is-active denaro-v3'
ssh marco@MARCODG1 'systemctl is-active denaro-v3'
```

---

## ⚠️ Azioni in sospeso

- [ ] **Verificare chiave Nuvola** — `-2008 Invalid Api-Key ID`
- [ ] **Trasferire capitale** da mc2orion a nuvolatrading (~$30) e marcodg1marcosol (~$30)
- [ ] **Fix equity calculation** — CircuitBreaker.update_equity() deve usare USDC totale + valore market SOL/DOGE/ADA
- [ ] **Test failover** — kill MC2 e verificare che Nuvola prenda il lock SOL/USDC
- [ ] **Zabbix: allineare item** per DOGE/USDC e ADA/USDC su host Nuvola e MARCODG1
- [ ] **Profit sharing** — riattivare con nuovo capitale

---

*Ultimo aggiornamento: 24 Giugno 2026, 14:10 CEST*
