# Audit Baseline — 2026-09-08

Congelato prima di qualsiasi modifica. Fonte di verità per il cambio di passo.

## Stato repo (mc2, /home/sergio/denaro)

- Branch: `main`
- HEAD: `e4e6155ee9fe419c4ed7bbf43bbfaec9fd748abf`
- Working tree: pulito
- Remote: `git@github.com:grivetto/alpha-omega-trading.git`

## Test

- Suite: 174 passed (pytest 9.1.1)
- `pytest-cov` NON installato (solo `pytest` nel venv)
- Nessun tool di qualità installato (no ruff/mypy/black/flake8)

## pyproject.toml — problemi noti

- `name = "alpha-omega-trading"` ma il package reale è `denaro/`
- `[tool.setuptools.packages.find] include = ["alpha_omega*", "config*", ...]` — NON include `denaro*`
- `version = "2.2.0"` — non verificato contro alcun changelog
- `license = "Unlicense"` ma README dice CC0 1.0 (incoerenza)
- `dependencies` elenca redis/asyncpg/sqlalchemy/ta-lib/prometheus/telegram — da verificare se davvero usati

## Config drift (critico)

- `config/strategy_overrides.json` → `paper:SOL/EUR` ha `capital: 50`, `strategy: vagr`
- I test `test_denaro_node.py` si aspettavano `capital: 100`
- Fix temporaneo applicato: `overrides_file: /tmp/nonexistent_overrides.json` nel test
- Questo è un accoppiamento implicito pericoloso da risolvere

## Config orfane in config/

- `node.yaml.bak.2bot`, `node.yaml.bak.cutover-bug`, `node.yaml.bak.sim500-20260827`
- `node_adaptive_vol_grid_paper.yaml`, `node_vagr_paper.yaml`, `node_trend*.yaml`, `node_paper.yaml`, `node.yaml`
- Nessuna etichetta ACTIVE/PAPER/LEGACY

## Stato runtime 3 nodi (foto 23:46 CEST)

### mc2 (questo host)
- `denaro-node-mc2` active/running — OKX DOGE/EUR + SOL/EUR (LIVE, €24)
- DOGE: equity €24.18, 1 buy, 5 sell, PnL +€0.016, 1 trade vinto
- SOL: equity €24.18, 3 trade, 3 vinti, PnL +€0.049
- `free_quote=0.1294` (quasi tutto in asset)

### MARCODG1 (87.106.222.123, user marco)
- `denaro-node-trend-live` active/running — Kraken SOL/EUR + XRP/EUR (LIVE, €25.4)
- SOL: equity €25.43, 1 buy, PnL +€0.997, 1 trade vinto
- XRP: equity €25.43, 1 buy, 0 trade
- **CRITICO**: entrambi `error = "PRE-FLIGHT BLOCK: preflight: min_notional 0.4500 > available 0.0169"`, `free_quote=0.0`
- Gira su codice VECCHIO (fix `e4e6155` non deployato)

### nuvola (87.106.3.15, user sergio)
- `denaro-node-nuvola` active/running ma NODO MORTO
- DOGE: `enabled: false` (chiave OKX morta 50119), health fermo 1 set, uptime 60s
- SOL Kraken: health fermo 24 ago, 0 trade, `enabled: false`
- Nessun tick recente nel journal

## Criticità aperte (in ordine di priorità)

1. MARCODG1 su codice vecchio — bot Kraken bloccati da preflight
2. nuvola nodo morto — da riattivare o decommissionare
3. README obsoleto — dice "4 bot Active" ma 2 sono degraded
4. Config drift `strategy_overrides.json` vs test
5. Nessun deploy automatizzato — SSH manuale
6. Nessuna copertura misurata — "174 passed" non dice quanto è coperto
7. pyproject.toml incoerente (name/license/packages/deps)
