# Money — Deploy

Deployment versionato del progetto Money (docs in `github.com/grivetto/money`,
qui l'implementazione `deploy/`). Tutto parametrizzato su `PROJECT_ROOT`
(e, per il banco, su `BANCO_USER`).

## Struttura

```
deploy/
├── templates/                      # unit systemd (placeholder {{PROJECT_ROOT}}, {{BANCO_USER}})
│   ├── money-banco-secco.service   #   banco a secco (oneshot, hardening)
│   ├── money-banco-secco.timer     #   ogni 5 minuti
│   ├── fleet-integrity.service     #   check integrita' flotta (gia' attivo su mc2)
│   └── fleet-integrity.timer       #   ogni 15 minuti
├── banco/
│   └── money_banco_secco.py        # la logica del banco (pura + I/O, testabile)
├── scripts/
│   ├── money_banco_secco.sh        # wrapper: venv + segreti, poi exec del modulo
│   └── install.sh                  # installer (--dry-run, guardie statiche)
├── tests/                          # guardie che girano in CI
│   ├── test_no_order_calls.py      #   l'invio ordini e' ASSENTE da deploy/
│   └── test_banco_logic.py         #   step_size, equity, guardia, metrica
└── README.md
```

## Prerequisiti (bloccante: e' un'azione di conto)

1. **Chiave dedicata SOLO Read** sul conto main OKX, creata dal proprietario:
   - Permessi: **solo Read** (niente trade, niente withdraw — la main puo' prelevare);
   - IP whitelist: `87.106.222.123` (MARCODG1); `87.106.3.15` (nuvola) se serve;
   - Hostname `eea.okx.com`.
2. `config/.env_banco` creato da `config/.env_banco.example` e `chmod 600`.
3. Capitale dichiarato REALE in `config/node_banco.yaml` (versionato). Al
   26/09/2026: **26,0030 EUR nel FUNDING**, trading `totalEq 0` — il banco
   legge entrambi e li riporta separati.

## Installazione

```bash
# 1. dry-run: mostra cosa verrebbe scritto (non tocca il sistema)
./deploy/scripts/install.sh --dry-run --node MARCODG1

# 2. installazione (serve sudo per systemd)
sudo ./deploy/scripts/install.sh --node MARCODG1

# 3. test manuale (collaudo: le 5 domande di docs/02 §6 si leggono dal log)
systemctl start money-banco-secco.service
journalctl -u money-banco-secco.service -n 60 --no-pager
```

L'installer esegue PRIMA le guardie statiche (nessuna chiamata di invio in
`deploy/`, bash -n, py_compile) e interpola `{{PROJECT_ROOT}}`/`{{BANCO_USER}}`.
Il timer parte da solo ogni 5 minuti (`systemctl list-timers | grep money`).

## Cosa fa il banco (e cosa NON fa)

Fa, in ordine (docs/02 §4): legge saldo **trading + funding** separati →
equity in EUR (EUR + valore mercato asset) → **guardia di capitale** (PASS /
`NON_FINANZIATO` con i tre numeri) → calcolo dell'ordine con
`floor(nozionale/prezzo/step)*step` (mai `int(step)`, che con 0.001 vale 0) →
stampa `DRY-RUN, NON INVIATO` con pedaggio assunto `okx_eea_spot` →
riconciliazione (ordini aperti, posizioni) → riga `METRICA` per Zabbix/aggregatore.

**NON invia ordini.** L'invio e' assente dal codice, non disattivato da un
flag; `deploy/tests/test_no_order_calls.py` lo verifica staticamente e la CI
lo esegue a ogni push. Con la chiave read-only del proprietario, "nessun
ordine" e' anche una proprieta' della credenziale: l'API rifiuterebbe.
Con `BANCO_RICHIEDI_READ_ONLY=1` il banco rifiuta (exit 5) chiavi con
trade/withdraw.

Codici di uscita: `0` ok · `2` NON_FINANZIATO/NON_FATTIBILE · `3`
autenticazione · `4` permessi/IP · `5` chiave non read-only (se richiesto)
· `1` altro errore.

## Guardie e test (CI)

```bash
# quello che esegue la job "guardie-deploy":
python -m pytest deploy/tests tools/tests -q

# verifica statica manuale (nessun risultato = nessun invio ordini):
grep -rn "create_order" deploy/banco deploy/scripts || echo "OK: nessun invio"
```

## Log e telemetria

- Journal: `journalctl -u money-banco-secco.service`
- jsonl: `PROJECT_ROOT/logs/banco_secco.jsonl` (una riga per esecuzione)
- file health: `PROJECT_ROOT/logs/banco_secco_health.json` (o `BANCO_HEALTH_PATH`)
- metrica: riga `METRICA banco_esito=... equity_eur=... equity_trading_eur=...
  equity_funding_eur=... capitale_dichiarato=... nozionale_eur=... qty=...
  pedaggio_assunto_pct=... tariffa=... chiave_perm=... ordini_aperti=...
  riconciliazione_quadra=...` — risponde alle 5 domande di docs/02 §6 dal
  solo log.

## Nodi target

Il banco gira dove la chiave e' whitelistata: **MARCODG1** (primario),
**nuvola** (secondario). **mc2: NO** (IP non in whitelist → 50119).

## Protocollo Git (Hermes + DSH)

- Prefisso commit: `[hermes]` per deploy/; `[dsh]` per il resto.
- Prima del push: `git fetch origin && git rebase origin/main`; mai force push.
