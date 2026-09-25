# Money — Deploy

Versioned deployment for the Money project (github.com/grivetto/money).
All systemd units, cron, and scripts are parameterized by `PROJECT_ROOT`.

## Structure

```
deploy/
├── templates/           # systemd unit templates (with {{PROJECT_ROOT}} placeholders)
│   └── money-banco-secco.service
├── scripts/
│   ├── install.sh       # Installer (supports --dry-run)
│   └── money_banco_secco.sh  # Banco di prova a secco (implements docs/02)
├── config/
│   ├── node_banco.yaml  # Banco node config
│   └── .env_banco.example  # Example env (owner must create real .env_banco with read-only key)
└── README.md            # This file
```

## Quick Start

```bash
# Dry-run to see what would change
./scripts/install.sh --dry-run --project-root /home/sergio/alpha-omega-trading

# Actual install (needs sudo for systemd)
sudo ./scripts/install.sh --project-root /home/sergio/alpha-omega-trading --node MARCODG1

# Test the banco
systemctl start money-banco-secco.service
journalctl -u money-banco-secco.service -f
```

## Prerequisites

1. **Chiave dedicata read-only** su conto main OKX (creata dal proprietario):
   - Permessi: **SOLO Read** (niente trade, niente withdraw)
   - IP Whitelist: `87.106.222.123` (MARCODG1), `87.106.3.15` (nuvola)
   - Hostname: `eea.okx.com`

2. **Configurazione reale**:
   ```bash
   cp config/.env_banco.example config/.env_banco
   # Riempi con la chiave read-only reale
   ```

3. **Conto main finanziato**: 26.0030 EUR in trading (verificato 2026-09-25), funding vuoto.

## Banco di prova a secco (spec: docs/02_banco_di_prova_a_secco.md)

Il banco **non invia ordini**. Fa:
1. Legge saldo reale (trading + funding separati)
2. Calcola equity in EUR (EUR + valore asset)
3. Guardia capitale: `equity >= capitale_dichiarato` → prosegue, altrimenti `NON_FINANZIATO` + exit code 2
4. Calcola ordine dry-run (nozionale = capitale × frazione, arrotondato a step_size)
5. Stampa ordine con etichetta `DRY-RUN, NON INVIATO`
6. Riconcilia: ordini aperti, posizioni
7. Log metrica (una riga per esecuzione)

**Divieti vincolanti** (testati staticamente):
- Nessun percorso chiama `create_order`
- Nessun LLM nel percorso caldo
- Nessun capitale dichiarato che il conto non ha
- Nessun prelievo

## Nodi target

Il banco gira dove la chiave read-only è whitelistata:
- **MARCODG1** (87.106.222.123) — primario
- **nuvola** (87.106.3.15) — secondario
- **mc2** — **NO** (IP non in whitelist)

## Verifica statica no-create_order

```bash
# Da PROJECT_ROOT
grep -r "create_order" deploy/ scripts/ --include="*.py" --include="*.sh" || echo "OK: nessun create_order"
```

## Log & Metriche

- Journal: `journalctl -u money-banco-secco.service -f`
- File health: `/home/sergio/denaro/health/banco_secco.json`
- Metrica Zabbix: `banco_esito=PASS|NON_FINANZIATO equity_eur=... capitale_dichiarato=...`

## Protocollo Git (Hermes + DSH)

- Prefisso commit: `[hermes]` per deploy/
- Prima di push: `git fetch origin && git pull --rebase origin main`
- Mai force push, mai `git checkout -f -B main origin/main`