# Audit integrale DENARO + AI — 2026-09-09 (v4 — con saldi reali e riconciliazione)
Solo LETTURA sugli exchange; nessun ordine eseguito.

## 1) Catena AI Hermes (mc2) — RISANATA e VERIFICATA
Crash utente: HTTP 410 end-of-life NVIDIA.
- model principale = MoA preset 'prod': aggregatore 'minimax-m3' EOL su NVIDIA 2026-09-09T09:00Z.
- fallback 'deepseek-ai/deepseek-v4-flash' (EOL 08-07) e 'qwen/qwen3-coder-480b' (EOL 06-11) -> 410.
Fix config-only (backup ~/.hermes/config.yaml.bak.20260909_191936):
- fallback: deepseek-v4-pro:gpt-oss-120b (FreeLLM mc2, live) + nvidia:nemotron-3-super-120b-a12b (live).
- preset MoA devel/prod/test -> aggregatore gpt-oss-120b; refs gpt-oss-120b/20b, gemini-3.5-flash-lite, gemini-3.1-flash-lite (tutti verificati live 0.1-1.7s). Config: 0 issue. E2E MoA prod OK; tool-call aggregatore OK.
- Cron 'Denaro Orchestratore Hermes-DS' pinnato a moa/prod (era drift-skip da 64 fallimenti). Gateway hermes riattivato (systemd user).

## 2) Saldi reali exchange (MARCODG1, .env live, read-only)
OKX_MAIN: EUR 1.00 | DOGE 9.98 | ETH/SOL/ADA ~0  -> quasi vuoto (~1 EUR).
MARCOSUB1 (OKX): EUR ~0.0000005 -> VUOTO.
KRAKEN (alias KRAKEN==TRENDSUB==NUVOLASUB1 -> STESSO conto): ADA 0.0644 | SOL 0.1413 | XRP 10.5387 | EUR 0.0169 | USD 0.4073.
Equity reale Kraken ~EUR 25.8 (prezzi live: SOL 88.98, XRP 1.22, ADA 0.187, USD->EUR 1.1636).

## 3) Riconciliazione ordini/posizioni
- Open orders REALI: 0 su OKX_MAIN, 0 su MARCOSUB1, 0 su KRAKEN (tutti i simboli) - i bot dichiarati 'running' NON piazzano ordini.
- trend-live Kraken: 2 bot momentum (SOL/XRP) sullo stesso conto dichiaravano entrambi equity ~25.45 -> doppio conteggio; EUR libero 0.0169 -> preflight block min_notional.
  AZIONE ESEGUITA (2026-09-09): XRP/EUR live DISABILITATO (enabled:false), resta SOL/EUR (1 bot per conto). Servizio denaro-node-trend-live riavviato; log conferma 'bot XRP/EUR disabilitato (config)'.
- OKX node.yaml: bot ADA/SOL/DOGE/ETH disabilitati su config MARCODG1 (chiavi morte 50119) - allineato a saldi reali (conto vuoto). CB spurio SOL segnalato.
- mc2: nodo paper/okx DOGE eq ~24.1, 6 sell, healthy (nodo separato).
- trades.db legacy su MARCODG1 fermo ad aprile 2026 (non usato dai motori nuovi).

## 4) Repo/config
HEAD git allineato locale==mc2==MARCODG1==origin/main. Config di deploy sincronizzati dai nodi live.


## 5) COMMIT GITHUB (per analisi Manus AI)
- branch main aggiornato: 4cce9c6 "fix(denaro): disabilita bot Kraken XRP live (1 bot per conto, resta SOL) + report audit allineamento AI/denaro"
- repo: https://github.com/grivetto/alpha-omega-trading (public)
- contenuto: config/node_trend_live_kraken.yaml (XRP live enabled:false) + docs/audit_allineamento_2026-09-09.md
- nota: config OKX (node.yaml/node_mc2.yaml/node_nuvola.yaml) gia' allineati su origin/main (chiavi morte 50119 disabilitate); non riattivati.
