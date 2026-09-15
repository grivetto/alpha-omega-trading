# Fleet Manifest — stato verificato della flotta Denaro

> **Data della verifica:** 2026-09-15 (SSH read-only su mc2, nuvola, MARCODG1)
> **Scopo:** questo documento è l'**unica fonte di verità** su cosa gira dove,
> con quale config e su quale conto. Se il codice contraddice questo file,
> il file va aggiornato *contestualmente* al commit.

Prima del 2026-09-15 non esisteva un documento equivalente: la mappa
host→servizio→config→conto era ricostruibile solo interrogando a mano tre
macchine, ed era già divergente dal repository.

---

## 1. Host e root di deploy

| Host | Ruolo | Root di deploy | Note |
|---|---|---|---|
| **mc2** | nodo live OKX + monitoraggio | `/home/sergio/alpha-omega-trading` | Desktop, dietro CGNAT. Contiene anche Zabbix, hermes, agent-zero |
| **nuvola** | nodo (chiavi non valide) | `/home/sergio/alpha-omega-trading` | VPS |
| **MARCODG1** | nodo live Kraken + dashboard | `/home/marco/alpha-omega-trading` | VPS, espone dashboard e Zabbix |

**Root legacy presenti (da dismettere, NON usare):**
`/home/sergio/denaro_node_app`, `/home/marco/denaro_node_app`,
`/home/sergio/denaro`, `/home/marco/denaro`.
Sono tre generazioni di deploy diverse. Al 2026-09-15 alcune unit systemd
puntavano ancora a `*_node_app`.

> **Regola:** un solo root di deploy per host = il checkout git
> `*/alpha-omega-trading`. Il codice in produzione deve essere
> **identico** al commit del branch.

---

## 2. Servizi e conti (stato verificato)

### mc2

| Unit | WorkingDirectory (deployato) | Config | Conto | Stato |
|---|---|---|---|---|
| `denaro-node-mc2` | alpha-omega-trading | `node_mc2.yaml` | OKX main (mc2) | **LIVE** — 12 sell aperti, €0,38 liberi |
| `denaro-node-nuvola` | denaro_node_app ⚠️ | `node_nuvola.yaml` | OKX (chiave morta 50119) | **DA FERMARE** |
| `denaro-node-trend` | alpha-omega-trading | `node_trend.yaml` | — (paper) | duplicato di MARCODG1 |
| `denaro-feeder-mc2` | denaro_node_app ⚠️ | `feeder.yaml` | — | ZeroMQ market data |
| `denaro-health-mc2` | denaro | — | — | HTTP :8911 |
| `denaro-aggregator-mc2` | alpha-omega-trading | — | — | HTTP :8912 |
| `denaro-dashboard-mc2` | alpha-omega-trading | — | — | HTTP :8913 |

### nuvola

| Unit | WorkingDirectory | Config | Conto | Stato |
|---|---|---|---|---|
| `denaro-node-nuvola` | alpha-omega-trading | `node_nuvola.yaml` | OKX (chiave invalida 50111) | inerte (tutti `enabled: false`) |
| `denaro-node-trend` | alpha-omega-trading | `node_trend.yaml` | — (paper) | duplicato di MARCODG1 |
| `denaro-health-nuvola` | denaro | — | — | HTTP :8911 |

### MARCODG1

| Unit | WorkingDirectory | Config | Conto | Stato |
|---|---|---|---|---|
| `denaro-node-trend-live` | alpha-omega-trading | `node_trend_live_kraken.yaml` | Kraken | **LIVE** — era drift: XRP `enabled: true` |
| `denaro-node-paper` | alpha-omega-trading | `node.yaml` | — (paper) | paper, free negativo (bug contabile) |
| `denaro-node-trend` | alpha-omega-trading | `node_trend.yaml` | — (paper) | **canonico** |
| `denaro-brain` | denaro | — | — | watchdog + strategy lab |
| `denaro-aggregator-marcodg1` | denaro | — | — | HTTP :8912 |
| `denaro-health-marcodg1` | denaro | — | — | HTTP :8911 |

---

## 3. Conti reali (mark-to-market, 2026-09-15)

| Conto | Asset | Valore stimato | Ordini aperti | Liquido |
|---|---|---|---|---|
| mc2 OKX | DOGE 262,95 + SOL 0,045 | ≈ €22,4 | **12 sell** (08–11/09, con duplicati) | €0,38 |
| MARCODG1 OKX (main) | €1,00 + DOGE 9,98 | ≈ €1,7 | 0 | €1,00 |
| MARCODG1 OKX (`MARCOSUB1_`) | — | €0 | 0 | €0 |
| Kraken (`MAIN`=`NUVOLASUB1_`=`TRENDSUB_`) | XRP 15,83 + ADA 0,064 + €6,10 + $0,41 | ≈ €23,9 | **3 sell XRP** | €6,10 |
| nuvola OKX | — | — | — | chiave invalida |
| **TOTALE** | | **≈ €48** | 15 ordini | **≈ €7,5** |

**PnL realizzato storico accertato: ≈ €0,38** (vedi `docs/10_backtest_onesto_e_findings.md`).

### Attenzione: conti alias

`KRAKEN_API_KEY`, `NUVOLASUB1_KRAKEN_*` e `TRENDSUB_KRAKEN_*` puntano allo
**stesso** conto Kraken. Tre nomi, un conto: qualunque ragionamento che sommi
i tre saldi conta il capitale tre volte.

---

## 4. Difetti strutturali aperti

| # | Difetto | Impatto |
|---|---|---|
| F1 | Unit systemd nel repo puntano a `*_node_app`; la produzione usa `alpha-omega-trading` | Il repo non descrive la produzione |
| F2 | Deploy non riproducibile (scp manuale, tree modificati non committati) | Deriva silenziosa (es. XRP live) |
| F3 | 3 root di deploy per host | Nessuno sa quale codice gira davvero |
| F4 | 3 istanze di `node_trend.yaml` (paper) su host diversi | CPU sprecata, stato divergente |
| F5 | Health senza mark-to-market | Le perdite non sono visibili |
| F6 | `denaro-node-paper`: `free` negativo nei tick | Bug contabile nel paper |

---

## 5. Stato obiettivo (target)

```
mc2        → denaro-node-mc2           (LIVE OKX)   + health/aggregator/dashboard
MARCODG1   → denaro-node-trend-live    (LIVE Kraken) + health/aggregator + brain
MARCODG1   → denaro-node-trend         (PAPER, validazione)
nuvola     → (nessun nodo di trading)  — solo health
```

**Un engine per conto. Un conto per engine. Un solo root di deploy.**

---

*Verificato con: `denaro/scripts/fleet_audit.sh` e `denaro/scripts/audit_balances.py`.*
