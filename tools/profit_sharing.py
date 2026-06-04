#!/usr/bin/env python3
"""
Denaro Profit-Sharing v1.0
Alle 23:59 di ogni giorno, calcola il 33% del profitto giornaliero
e lo trasferisce al sub-account sergio@grivetto.eu
Dal 4 Maggio 2026 — "a prova di bomba"
"""
import ccxt, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

# === CONFIG ===
PROFIT_PCT = 0.33  # 33%
TARGET_EMAIL = "sergio@grivetto.eu"

# Master key per trasferire fondi
MASTER_KEY = "fRD2vQLKTx4sq5xXkN4zdEXeylgyEwGE1ZP4CdnlTzL2svSCLK0k0Vc3W7QzFpW9"
MASTER_SECRET = "H8PryLwBsHHIlOSAnLSbwxSXujbs7uCTTmJhwe76uf9Com0Pg5sXI8S8ZcHZzeRz"

BASE_DIR = Path.home() / "denaro"
PROFIT_LOG = BASE_DIR / "profit_sharing.log"
STATE_FILE = BASE_DIR / ".profit_state.json"

# === SUB-ACCOUNT KEYS per leggere bilanci ===
NODES = {
    "nuvola": {
        "key": "FJoAq511YBJoxjnH0C7pc1stQC03CwbtBSXuz5UZW4xsdt6qwodhMLmJRVt8gGW2",
        "secret": "kPCtbXLrnQVwP6cSdPw3vXMo0Xn4RaofdF5QCmT882OJVFOJSU6kAVtF7tA7ZPOx",
    },
    "marcodg1": {
        "key": "tysQk9u0VGBdguX3wjmJwMaezSrpKVtBmpKG3cmy08ejuJuvuyBokLxSWEZAOJPD",
        "secret": "t5EZw0fCjjRsAEX7DZPoEvQTYsQ1CYVNxFutgeBvGuLYAqtR49X3zGGeQQ8QJY8a",
    },
    "mc2": {
        "key": "bTBXg4qjzYHkiXeAcVN3q68Io0R5P1Q6dPGcUVtFCYsjVK8jkFjq3xeanzbUCmCr",
        "secret": "PdfopnISeFXI6qmL9bLLaD23oH3BcYVttoKEJA5ycJuMbDOEpTzp8mm5Gk9u7GEx",
    },
}


def log(msg):
    """Scrive su file di log con timestamp"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(PROFIT_LOG, "a") as f:
        f.write(line + "\n")


def get_total_value(exchange, node_name):
    """Calcola il valore totale in USDT del sub-account"""
    try:
        bal = exchange.fetch_balance()
        free = {k: v for k, v in bal["free"].items() if v > 0.0001}
        total_usdt = 0.0

        # Prezzi in tempo reale
        prices = {}
        for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "DOGE/USDT", "BNB/USDT"]:
            try:
                t = exchange.fetch_ticker(symbol)
                prices[symbol] = t["last"]
            except:
                pass

        for asset, amount in free.items():
            if asset == "USDT" or asset == "USDC":
                total_usdt += amount
            elif asset == "EUR":
                total_usdt += amount * 1.08  # approx EUR/USD
            else:
                pair = f"{asset}/USDT"
                if pair in prices:
                    total_usdt += amount * prices[pair]

        return round(total_usdt, 2), free
    except Exception as e:
        log(f"  ERRORE lettura bilancio {node_name}: {e}")
        return 0.0, {}


def main():
    log("=" * 50)
    log("PROFIT-SHARING RUN")
    log(f"Target: {TARGET_EMAIL} | Split: {PROFIT_PCT*100:.0f}%")

    # Leggi stato precedente
    state = {}
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
        except:
            pass

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_value = state.get(f"{today}_value", 0)

    # Calcola valore totale corrente
    total_value = 0.0
    for node_name, creds in NODES.items():
        try:
            ex = ccxt.binance({
                "apiKey": creds["key"],
                "secret": creds["secret"],
                "options": {"defaultType": "spot"},
                "enableRateLimit": True,
            })
            val, _ = get_total_value(ex, node_name)
            total_value += val
            log(f"  {node_name}: ${val:.2f}")
        except Exception as e:
            log(f"  ERRORE {node_name}: {e}")

    log(f"TOTALE: ${total_value:.2f}")

    # Se è la prima run, salva come baseline
    if "baseline" not in state:
        state["baseline"] = total_value
        state["baseline_date"] = today
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        log(f"Baseline impostata: ${total_value:.2f} dal {today}")
        log("PROSSIMA ESECUZIONE: 23:59 di domani")
        return

    # Calcola profitto
    baseline = state.get("baseline", total_value)
    profit = round(total_value - baseline, 2)

    if profit <= 0:
        log(f"Nessun profitto oggi (variazione: ${profit:.2f}). Nessun trasferimento.")
        # Aggiorna baseline
        state["baseline"] = total_value
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        return

    # Calcola 33%
    transfer_amount = round(profit * PROFIT_PCT, 2)
    if transfer_amount < 1.0:
        log(f"Profitto: ${profit:.2f} → 33% = ${transfer_amount:.2f} (troppo piccolo, minimo $1)")
        state["baseline"] = total_value
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        return

    log(f"Profitto: ${profit:.2f} → 33% = ${transfer_amount:.2f}")
    log(f"Trasferimento ${transfer_amount:.2f} USDC a {TARGET_EMAIL}...")

    # Esegui trasferimento via master key
    try:
        ex_master = ccxt.binance({
            "apiKey": MASTER_KEY,
            "secret": MASTER_SECRET,
            "options": {"defaultType": "spot"},
            "enableRateLimit": True,
        })

        result = ex_master.sapi_post_sub_account_universaltransfer({
            "fromEmail": "nuvolatrading_virtual@2lyv5fu2noemail.com",
            "toEmail": TARGET_EMAIL,
            "fromAccountType": "SPOT",
            "toAccountType": "SPOT",
            "asset": "USDC",
            "amount": str(transfer_amount),
        })
        log(f"✅ Trasferito ${transfer_amount:.2f} USDC a {TARGET_EMAIL}!")
    except Exception as e:
        log(f"❌ ERRORE trasferimento: {e}")
        # Fallback: prova a trasferire dal master invece
        try:
            result = ex_master.sapi_post_sub_account_universaltransfer({
                "fromAccountType": "SPOT",
                "toEmail": TARGET_EMAIL,
                "toAccountType": "SPOT",
                "asset": "USDC",
                "amount": str(transfer_amount),
            })
            log(f"✅ (fallback) Trasferito ${transfer_amount:.2f} USDC da MASTER a {TARGET_EMAIL}!")
        except Exception as e2:
            log(f"❌ ERRORE anche fallback: {e2}")

    # Aggiorna baseline
    state["baseline"] = total_value
    state["last_transfer"] = {"date": today, "amount": transfer_amount}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    log("PROFIT-SHARING COMPLETATO ✓")


if __name__ == "__main__":
    main()
