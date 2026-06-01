# Denaro – findings.md
_Ricerca, vincoli, errori noti._

## Scoperte 2026‑05‑29
- Il sistema Denaro è già operativo su tre nodi (mc2, Nuvola, MARCODG1) con squadra orchestratore + bot.
- Sistema legacy (denaro_strategies, config_supervisor, metrics_collector) convive con momentum_scalper nuovo.
- Dashboard su https://sgrivett.ddns.net/denaro/ — servita da Nuvola (nginx), JSON provenienti da mc2 via cron.
- File nuvola.json viene sovrascritto dal vecchio metrics_collector (BUG noto).
- Capitale totale 242 €, EUR libero 5.63 € — capital protection mode attiva (± 200€).
- API Binate whitelistata con IP 93.43.252.114, endpoint api1.binance.com.
- Cron attivi: health‑monitor (h), pnl‑aggregator (15 min), Zabbix healer (5 min).

## Vincoli
- Non depositare più euro (Sergio ha detto "non deposito più EUR").
- Priorità: tutelare i ~200€ rimanenti — zero tolleranza a perdite.
- modalità analisi → diagnosi e report; modifiche a file solo su richiesta esplicita.
