# 🗄️ legacy/ — Architetture storiche (non più attive)

Questa cartella contiene le architetture e i motori **non più utilizzati** dal progetto.
Sono conservati per storia e riferimento — **il codice attivo è in `denaro/`**.

## Contenuto

| Percorso | Cosa era | Perché è legacy |
|---|---|---|
| `alpha_omega/` | Vecchio motore fleet multi-bot | Sostituito da `denaro/engine_solo_v33.py` (un motore, una coppia per bot) |
| `airdrop-farm/` | Farming airdrop autonomo | Progetto separato abbandonato |
| `neo/` | Prototipo async memory-first | Mai andato in produzione |
| `enhanced/` | Dashboard/health vecchi | Sostituiti da `denaro/` + dashboard web |
| `tests/` | Test delle architetture legacy | Test del motore attuale in `test_v7.py` |
| `kraken_engine.py`, `mexc_engine.py`, `bybit_engine.py` | Engine per singoli exchange | Unificati nel motore v3.3 |
| `shadowgrid_fleet.py`, `mock_runner.py`, `pair_scanner.py` | Componenti del vecchio fleet | Rimpiazzati |
| `main.py`, `run.py`, `deploy.sh` | Entry point vecchi | Il motore gira via systemd (`systemd/`) |
| `ARCHITECTURE*.md`, `SESSION_HANDOFF.md`, `RUNBOOK.md` | Documentazione delle vecchie versioni | Sostituite da `README.md` e `REPORT_NON_GUADAGNA.md` |

## Nota

Questa cartella documenta un anno di tentativi (con OpenClaw, Hermes, Agent Zero,
DeepSeek TUI) prima di arrivare a DENARO. La lezione: **il problema non era mai il
codice — era il capitale piccolo e l'assenza di edge verificato**.
