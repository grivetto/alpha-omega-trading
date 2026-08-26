"""Brain Alpha-Omega — configurazione centrale.

Il Brain gira su MARCODG1 (unico host con ssh verso nuvola e mc2) e
verifica/ripara l'ambiente Denaro, sviluppa strategie e parla con Hermes.
SOLO stdlib: subprocess(ssh) + urllib (Zabbix trapper, OHLCV public).
"""
from __future__ import annotations

import json
from pathlib import Path

# ── dove vive il brain su MARCODG1 ──────────────────────────────────────────
BRAIN_DIR = Path(__file__).resolve().parent
LOG_DIR = BRAIN_DIR / "logs"
DATA_DIR = BRAIN_DIR / "data"
STATE_FILE = DATA_DIR / "brain_state.json"       # ultimo stato raccolto
REPAIR_LOG = LOG_DIR / "repairs.jsonl"
HERMES_LOG = LOG_DIR / "hermes_conv.md"
GIT_REPO = Path("/home/marco/alpha-omega-brain")  # clone della repo (origine: origin/main)

# ── macchine ─────────────────────────────────────────────────────────────────
# ssh: lista argomenti per `ssh -o BatchMode=yes ...` ([] = locale)
MACHINES = {
    "marcodg1": {"ssh": [], "sudo": True},
    "nuvola":   {"ssh": ["sergio@87.106.3.15"], "sudo": True},
    "mc2":      {"ssh": ["sergio@127.0.0.1", "-p", "2222"], "sudo": True},  # tunnel inverso
}

# unit systemd da tenere attive per macchina
UNITS = {
    "marcodg1": ["denaro-node-paper", "denaro-node-trend",
                 "denaro-health-marcodg1",
                 "denaro-aggregator-marcodg1", "zabbix-agent"],
    "nuvola":   ["denaro-node-nuvola", "denaro-health-nuvola",
                 "zabbix-agent", "zabbix-tunnel"],
    "mc2":      ["denaro-node-mc2", "denaro-feeder-mc2", "denaro-health-mc2",
                 "zabbix-agent", "zabbix-tunnel-reverse"],
}

# processi critici per macchina (pgrep -f; [] evita self-match)
PROCESSES = {
    "marcodg1": ["[d]enaro.denaro_node"],
    "nuvola":   ["[d]enaro.denaro_node"],
    "mc2":      ["[d]enaro.denaro_node", "[d]enaro.infrastructure.mc2_feeder",
                 "[h]ermes_cli.main gateway run"],
}

# bot → (macchina, unit che lo ospita, health file)
# bot_key = mode:env_prefix:symbol (coerente con denaro_node.bot_key)
BOTS = {
    # MARCODG1 — live OKX main + marcosub1 + Kraken
    ("marcodg1", "okx:ADA/EUR"):   ("denaro-node-paper", "/home/marco/denaro/health/ada.json"),
    ("marcodg1", "okx:SOL/EUR"):   ("denaro-node-paper", "/home/marco/denaro/health/sol.json"),
    ("marcodg1", "okx:DOGE/EUR"):  ("denaro-node-paper", "/home/marco/denaro/health/doge.json"),
    ("marcodg1", "okx:ETH/EUR"):   ("denaro-node-paper", "/home/marco/denaro/health/eth.json"),
    ("marcodg1", "kraken:SOL/EUR"):("denaro-node-paper", "/home/marco/denaro/health/sol_kraken.json"),
    # MARCODG1 — paper (stesso Node)
    ("marcodg1", "paper:ADA/EUR"):  ("denaro-node-paper", "/home/marco/denaro_node_app/node_data/paper_default_ADA_EUR_health.json"),
    ("marcodg1", "paper:SOL/EUR"):  ("denaro-node-paper", "/home/marco/denaro_node_app/node_data/paper_default_SOL_EUR_health.json"),
    ("marcodg1", "paper:XRP/EUR"):  ("denaro-node-paper", "/home/marco/denaro_node_app/node_data/paper_default_XRP_EUR_health.json"),
    ("marcodg1", "paper:DOGE/EUR"): ("denaro-node-paper", "/home/marco/denaro_node_app/node_data/paper_default_DOGE_EUR_health.json"),
    ("marcodg1", "paper:ETH/EUR"):  ("denaro-node-paper", "/home/marco/denaro_node_app/node_data/paper_default_ETH_EUR_health.json"),
    # MARCODG1 — istanza TREND (momentum + adaptive scalper, paper)
    ("marcodg1", "trend:paper:SOL/EUR"): ("denaro-node-trend", "/home/marco/denaro_node_app/node_data_trend/paper_default_SOL_EUR_health.json"),
    ("marcodg1", "trend:paper:ETH/EUR"): ("denaro-node-trend", "/home/marco/denaro_node_app/node_data_trend/paper_default_ETH_EUR_health.json"),
    ("marcodg1", "trend:paper:ADA/EUR"): ("denaro-node-trend", "/home/marco/denaro_node_app/node_data_trend/paper_default_ADA_EUR_health.json"),
    ("marcodg1", "trend:paper:XRP/EUR"): ("denaro-node-trend", "/home/marco/denaro_node_app/node_data_trend/paper_default_XRP_EUR_health.json"),
    # NUVOLA — live nuvolasub1 + paper
    ("nuvola", "okx:DOGE/EUR"): ("denaro-node-nuvola", "/home/sergio/denaro/health/doge_nuvola.json"),
    ("nuvola", "paper:ADA/EUR"): ("denaro-node-nuvola", "/home/sergio/denaro_node_app/node_data/paper_default_ADA_EUR_health.json"),
    ("nuvola", "paper:SOL/EUR"): ("denaro-node-nuvola", "/home/sergio/denaro_node_app/node_data/paper_default_SOL_EUR_health.json"),
    ("nuvola", "paper:XRP/EUR"): ("denaro-node-nuvola", "/home/sergio/denaro_node_app/node_data/paper_default_XRP_EUR_health.json"),
    # MC2 — live mc2sub1 + paper
    ("mc2", "okx:DOGE/EUR"): ("denaro-node-mc2", "/home/sergio/denaro/health/doge_mc2.json"),
    ("mc2", "paper:ADA/EUR"): ("denaro-node-mc2", "/home/sergio/denaro_node_app/node_data/paper_default_ADA_EUR_health.json"),
    ("mc2", "paper:SOL/EUR"): ("denaro-node-mc2", "/home/sergio/denaro_node_app/node_data/paper_default_SOL_EUR_health.json"),
    ("mc2", "paper:XRP/EUR"): ("denaro-node-mc2", "/home/sergio/denaro_node_app/node_data/paper_default_XRP_EUR_health.json"),
}

# ── soglie ───────────────────────────────────────────────────────────────────
HEALTH_STALE_S = 180.0     # health file piu' vecchio di questo → bot morto
UNIT_CHECK_LOOP_S = 60.0   # ciclo base del watchdog
REPAIR_COOLDOWN_S = 600.0  # min. secondi tra due riparazioni della stessa unit
REPAIR_MAX_PER_HOUR = 3    # max riavvii/ora per unit
NODE_RESTART_COOLDOWN_S = 1800.0  # max 1 restart nodo/30min (promozioni strategie)

# ── Zabbix (trapper API raggiungibile da MARCODG1 via tunnel 1080) ──────────
ZABBIX_API = "http://127.0.0.1:1080/api_jsonrpc.php"
ZABBIX_USER = "Admin"
ZABBIX_PASS = "zabbix"
ZABBIX_HOSTS = {"marcodg1": "MARCODG1", "nuvola": "nuvola", "mc2": "mc2"}

# ── Hermes (ponte su mc2) ────────────────────────────────────────────────────
HERMES_INBOX = "/home/sergio/hermes_bridge/inbox.md"
HERMES_OUTBOX = "/home/sergio/hermes_bridge/outbox.md"
HERMES_RUNNER = "/home/sergio/hermes_bridge/run_hermes.sh"  # script su mc2
HERMES_INTERVAL_S = 1800.0   # ciclo di scambio con Hermes ogni 30 min
HERMES_TIMEOUT_S = 600.0     # timeout per `hermes -z` (LLM lento)

# ── Strategy Lab ─────────────────────────────────────────────────────────────
STRATEGY_INTERVAL_S = 6 * 3600.0   # runde di backtest ogni 6h
PAPER_VALIDATE_H = 24.0            # un candidato paper si valuta dopo 24h
PROMOTE_MARGIN = 1.3               # il candidato deve battere il baseline ×1.3
# artefatti strategie DENTRO la repo clonata su MARCODG1 (committati dal Brain)
REGISTRY_PATH = GIT_REPO / "config" / "strategies" / "registry.json"
OVERRIDES_PATH = GIT_REPO / "config" / "strategy_overrides.json"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
