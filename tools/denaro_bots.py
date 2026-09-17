#!/usr/bin/env python3
"""Denaro — registro UNICO dei bot in produzione (15: 5 per macchina).

Perche' esiste: il pusher Zabbix e il setup degli host Zabbix devono parlare
degli STESSI bot. Prima erano due elenchi separati e sono andati fuori sync: il
pusher spingeva ancora i 3 bot della generazione precedente (nuvola_sol,
marcodg1_xrp), i cui file health erano fermi da giorni. Zabbix vedeva "nessun
dato da 5 minuti" e l'autohealing riavviava il nodo nuvola OGNI 2 MINUTI, in
loop: un trigger stantio con un nodo perfettamente sano.

Ogni voce: (slug, asset, macchina, sorgente).
- slug    = prefisso delle chiavi Zabbix (bot.<slug>.<metrica>)
- sorgente = ("file", path) locale su mc2 oppure ("ssh", alias, path) remoto
"""
from __future__ import annotations

HEALTH = "/home/sergio/denaro/health"
HEALTH_MARCO = "/home/marco/denaro/health"

# (slug, asset, macchina, sorgente)
BOTS = [
    ("mc2_btc",      "BTC",  "mc2",      ("file", HEALTH + "/btc_mc2.json")),
    ("mc2_eth",      "ETH",  "mc2",      ("file", HEALTH + "/eth_mc2.json")),
    ("mc2_sol",      "SOL",  "mc2",      ("file", HEALTH + "/sol_mc2.json")),
    ("mc2_xrp",      "XRP",  "mc2",      ("file", HEALTH + "/xrp_mc2.json")),
    ("mc2_doge",     "DOGE", "mc2",      ("file", HEALTH + "/doge_mc2.json")),
    # aggiunti 2026-09-17 (round 17): allargare l'universo da 15 a 19 asset porta,
# nel simulatore a capitale condiviso, il rendimento di periodo da +34.90% a
# +48.89% e lo Sharpe da 0.79 a 1.06, col drawdown che SCENDE e zero segnali
# rifiutati. Ogni asset aggiunto migliora da solo.
    ("mc2_trx",      "TRX",  "mc2",      ("file", HEALTH + "/trx_mc2.json")),
    ("mc2_crv",      "CRV",  "mc2",      ("file", HEALTH + "/crv_mc2.json")),

    ("nuvola_link",  "LINK", "nuvola",   ("ssh", "nuvola",   HEALTH + "/link_nuvola_live.json")),
    ("nuvola_avax",  "AVAX", "nuvola",   ("ssh", "nuvola",   HEALTH + "/avax_nuvola_live.json")),
    ("nuvola_dot",   "DOT",  "nuvola",   ("ssh", "nuvola",   HEALTH + "/dot_nuvola_live.json")),
    ("nuvola_uni",   "UNI",  "nuvola",   ("ssh", "nuvola",   HEALTH + "/uni_nuvola_live.json")),
    ("nuvola_mina",  "MINA", "nuvola",   ("ssh", "nuvola",   HEALTH + "/mina_nuvola_live.json")),
    ("nuvola_sui",   "SUI",  "nuvola",   ("ssh", "nuvola",   HEALTH + "/sui_nuvola_live.json")),

    ("marcodg1_ada",  "ADA",  "MARCODG1", ("ssh", "MARCODG1", HEALTH_MARCO + "/ada_marcodg1_live.json")),
    ("marcodg1_arb",  "ARB",  "MARCODG1", ("ssh", "MARCODG1", HEALTH_MARCO + "/arb_marcodg1_live.json")),
    ("marcodg1_xlm",  "XLM",  "MARCODG1", ("ssh", "MARCODG1", HEALTH_MARCO + "/xlm_marcodg1_live.json")),
    ("marcodg1_algo", "ALGO", "MARCODG1", ("ssh", "MARCODG1", HEALTH_MARCO + "/algo_marcodg1_live.json")),
]

# Host Zabbix e chiave per ogni bot.
def host_of(slug: str) -> str:
    return "alpha-omega-bot-" + slug.replace("_", "-")


def key_of(slug: str, metrica: str) -> str:
    return "bot.%s.%s" % (slug, metrica)


# (suffisso chiave, etichetta, value_type, unita')
# value_type Zabbix: 0=float, 3=unsigned int, 4=text. Tutti item TRAPPER (type=2).
METRICHE = [
    ("adx",           "ADX",                       0, ""),
    ("atr_pct",       "ATR %",                     0, "%"),
    ("buys",          "ordini buy aperti",         3, ""),
    ("calmar",        "calmar",                    0, ""),
    ("cap_available", "capitale disponibile EUR",  0, "EUR"),
    ("cap_locked",    "capitale impegnato EUR",    0, "EUR"),
    ("drawdown",      "drawdown max",              0, ""),
    ("ema200",        "EMA200",                    0, ""),
    ("equity",        "equity EUR",                0, "EUR"),
    ("error",         "ultimo errore",             4, ""),
    ("free",          "free EUR",                  0, "EUR"),
    ("hurst",         "Hurst",                     0, ""),
    ("kelly",         "kelly fraction",            0, ""),
    ("losses",        "trade perdenti",            3, ""),
    ("pnl",           "PnL realizzato EUR",        0, "EUR"),
    ("profit_factor", "profit factor",             0, ""),
    ("regime",        "regime (stringa)",          4, ""),
    ("rsi",           "RSI",                       0, ""),
    ("sells",         "ordini sell aperti",        3, ""),
    ("sharpe",        "sharpe",                    0, ""),
    ("sortino",       "sortino",                   0, ""),
    ("status",        "status (1=running)",        3, ""),
    ("stop_loss",     "stop loss scattato",        3, ""),
    ("strategy",      "strategia",                 4, ""),
    ("trades",        "trade completati",          3, ""),
    ("uptime",        "uptime secondi",            3, "s"),
    ("volume",        "volume scambiato EUR",      0, "EUR"),
    ("win_rate",      "win rate %",                0, "%"),
    ("wins",          "trade vincenti",            3, ""),
]

# Metriche di TESTO: si pusha anche la stringa vuota, per PULIRE il valore
# quando il problema e' risolto (altrimenti un errore vecchio resta sull'item
# per sempre e il trigger continua a scattare).
TESTUALI = ("strategy", "regime", "error")

# Campo del file health -> suffisso chiave.
MAPPA = [
    ("equity", "total_equity"), ("free", "free_quote"), ("pnl", "pnl"),
    ("volume", "volume"), ("trades", "trades"), ("wins", "wins"),
    ("losses", "losses"), ("buys", "buys"), ("sells", "sells"),
    ("drawdown", "drawdown"), ("uptime", "uptime"), ("cap_locked", "cap_locked"),
    ("cap_available", "cap_available"), ("win_rate", "win_rate_pct"),
    ("profit_factor", "profit_factor"), ("sharpe", "sharpe"),
    ("sortino", "sortino"), ("calmar", "calmar"), ("kelly", "kelly"),
    ("adx", "adx"), ("atr_pct", "atr_pct"), ("rsi", "rsi"),
    ("ema200", "ema200"), ("hurst", "hurst"), ("strategy", "strategy"),
    ("regime", "regime"), ("error", "error"),
]

# Oltre questa eta' (secondi) il file health e' considerato FERMO e il bot
# viene segnalato come non in esecuzione. Senza questo controllo, un file
# vecchio continuerebbe a essere pushato con status=1 e un nodo morto
# sembrerebbe vivo: il trigger "nodata" non scatterebbe mai perche' il pusher
# tiene fresco l'item.
STALE_DOPO_S = 300
