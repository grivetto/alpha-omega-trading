# DENARO — Architettura Unificata (decisione: unire Denaro + ATLAS)

> Dopo il consolidamento della Fase 3, la scelta architetturale e': **UN SOLO
> motore di trading** (il Node Denaro asyncio) per TUTTI gli ambienti.
> ATLAS viene dismesso come sistema autonomo: i suoi fondi restano intatti
> sull'exchange e saranno gestiti dal Node.

---

## 1. Perche' unire (e non coesistere)

| Criterio | Node Denaro (Fase 3) | ATLAS (dismesso) |
|----------|----------------------|------------------|
| Stato | 109 test verdi, parita' M7 sul campo, WS, risk, storage | Mai tradato: `notional 3.33 < min_notional 5.0` da giorni |
| Capitale gestito | paper 500€ + 3 bot live v3.3 (~55€) | account Kraken dedicato (~26€ in SOL/ADA) con **0.83€ EUR** |
| Risk | circuit breaker azionato, pre-flight, SafeMode 3 livelli | risk passivo (check-only) |
| Persistenza | journal fsync + stato atomico + SQLite WAL | solo posizioni in memoria |
| Monitoraggio | Zabbix push + auto-heal cron + WS heartbeat | health HTTP solo |
| Manutenibilita' | 1 repo, 1 config, 1 unit | 1 repo separato, config duplicata |

Unire elimina il doppio motore, la doppia configurazione e il rischio di
conflitti (lezione del doppio bot Kraken): **un solo motore, N account**.

---

## 2. Struttura unificata

```
repo (github.com/grivetto/alpha-omega-trading)
├── denaro/                    # UNICO motore (Node asyncio)
│   ├── denaro_node.py         # entry point: python -m denaro.denaro_node --config config/node.yaml
│   ├── domain/                # types, indicators, risk, grid (puro)
│   ├── application/           # orchestrator, supervisor, safemode, config
│   ├── infrastructure/        # market_data, execution, rate_limiter, storage,
│   │   └── exchanges/         #   okx (EEA), kraken, paper
│   └── tests/                 # 109 test verdi
├── config/
│   └── node.yaml              # config UNICA: paper + OKX main + marcosub1 + Kraken + ex-ATLAS
├── systemd/                   # unit per ogni nodo (MARCODG1, nuvola)
├── zabbix/                    # push_metrics (con auto-heal), heal script, setup
└── legacy/                    # alpha_omega, airdrop-farm, enhanced, neo, atlas, denaro_v67
```

### Config unica, multi-account (`config/node.yaml`)
- `env_prefix` per-bot: `""` (OKX main), `MARCOSUB1_` (OKX marcosub1),
  `KRAKEN_` (Kraken Denaro), `ATLAS_` (Kraken ex-ATLAS).
- Chiavi SOLO da EnvironmentFile (${VAR} interpolate da Pydantic), mai nel file.
- `enabled: false` sui bot live finche' il cutover non e' approvato.

---

## 3. Stato ambienti dopo la pulizia

| Ambiente | Prima | Ora |
|----------|-------|-----|
| Nuvola | ATLAS (engine+watchdog) + denaro-kraken-sol v3.3 | ATLAS **fermato e disabilitato**; kraken-sol v3.3 attivo |
| MARCODG1 | Node paper (node_paper.yaml) + 6 unit v3.3 | invariato (Node paper attivo) |
| mc2 | Zabbix | invariato |

Fondi: OKX main (~8.7€), OKX marcosub1 (~21€), Kraken Denaro (~25€),
Kraken ATLAS (~26€ in SOL/ADA). **Nessun fondo spostato.**

---

## 4. Piano di migrazione residuo (cutover, richiede approvazione)

1. **Deploy node.yaml** sul Node (stessi paper; live disabilitati).
2. **Cutover OKX** (ADA marcosub1 + SOL main): fermare i v3.3, `enabled: true`
   nel node.yaml, riavvio Node, verifica riconciliazione ordini.
3. **Cutover Kraken Denaro**: idem su nuvola.
4. **Attivazione ex-ATLAS**: `enabled: true` per il bot SOL/EUR con
   `env_prefix: ATLAS_` (dopo il cutover OKX verificato). La strategia
   dell'ex-ATLAS era rotta (BTC/EUR senza EUR): il Node la sostituisce con
   un grid SOL/EUR dimensionato sul capitale reale.
5. **Dismissione v3.3**: rimozione unit engine_solo/engine_paper.
6. **Rollback** < 2 min (riattivare i v3.3) a ogni step.

---

## 5. Regole operative (mai violate)

- **Mai due motori sullo stesso conto** (lezione del doppio bot Kraken).
- Chiavi mai nel config versionato (solo env).
- Ogni modifica del motore: test verdi prima del deploy.
- Ogni cutover: gating di parita' 48h + rollback pronto.
