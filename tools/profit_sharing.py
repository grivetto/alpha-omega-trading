#!/usr/bin/env python3
"""
Denaro Profit Sharing — eseguito alle 23:59 ogni giorno
Trasferisce il 33% del profitto giornaliero a sergio@grivetto.eu
"""
import os, sys, time, logging
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("DENARO_HOME", "/home/sergio/denaro"))
sys.path.insert(0, str(HOME))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("profit_sharing")

# ===== CONFIG =====
PROFIT_SHARE_PCT = 0.33          # 33% del profitto giornaliero
DESTINATION_EMAIL = "sergio@grivetto.eu"
SAFETY_MIN_USDC = 5.0            # Non trasferire se il saldo scende sotto questa soglia

def load_api_keys():
    """Carica le API key dal .env del nodo"""
    key = secret = ""
    env_file = HOME / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "BINANCE_API_KEY" in line and "SECRET" not in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key = parts[1].strip().strip("'").strip('"')
                if "BINANCE_API_SECRET" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        secret = parts[1].strip().strip("'").strip('"')
    return key, secret


def get_total_equity(exchange) -> float:
    """Calcola il valore totale del portafoglio in USDT"""
    try:
        bal = exchange.fetch_balance()
        total = 0.0
        prices = {}
        
        # Prezzi per asset non-USDT/USDC
        for sym in ["BTC/USDT", "SOL/USDT", "ADA/USDT", "ETH/USDT", "BNB/USDT", "DOGE/USDT"]:
            try:
                prices[sym] = exchange.fetch_ticker(sym)["last"]
            except:
                pass
        
        for asset, qty in bal.get("total", {}).items():
            if not qty or qty <= 1e-8:
                continue
            if asset in ("USDT", "USDC"):
                total += qty
            elif asset == "EUR":
                total += qty * 1.15
            else:
                pair = f"{asset}/USDT"
                total += qty * prices.get(pair, 0)
        
        return total
    except Exception as e:
        log.error(f"Failed to get total equity: {e}")
        return 0.0


def transfer_to_master(exchange, amount_usdt: float):
    """Trasferisce USDT dal sub-account al master account"""
    try:
        # Binance sub-account transfer: sapi_post_sub_account_universaltransfer
        exchange.sapi_post_sub_account_universaltransfer({
            "fromEmail": "",          # sub-account (automatico)
            "toEmail": DESTINATION_EMAIL,
            "asset": "USDT",
            "amount": round(amount_usdt, 2),
        })
        log.info(f"✅ Trasferiti {amount_usdt:.2f} USDT a {DESTINATION_EMAIL}")
        return True
    except Exception as e:
        log.error(f"❌ Trasferimento fallito: {e}")
        return False


def read_last_equity():
    """Legge l'equity baseline salvata ieri"""
    baseline_file = HOME / ".daily_baseline"
    if baseline_file.exists():
        try:
            return float(baseline_file.read_text().strip())
        except:
            pass
    return 0.0


def save_baseline(equity: float):
    """Salva l'equity baseline per domani"""
    (HOME / ".daily_baseline").write_text(f"{equity:.2f}")


def main():
    log.info("=" * 50)
    log.info(f"PROFIT SHARING — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log.info("=" * 50)
    
    api_key, api_secret = load_api_keys()
    if not api_key:
        log.error("API keys non trovate. Abort.")
        sys.exit(1)
    
    import ccxt
    exchange = ccxt.binance({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })
    
    # 1. Calcola equity attuale
    current_equity = get_total_equity(exchange)
    log.info(f"Equity attuale: {current_equity:.2f} USDT")
    
    # 2. Leggi baseline di ieri
    yesterday_equity = read_last_equity()
    if yesterday_equity == 0:
        # Prima esecuzione: salva baseline e non trasferire
        log.info("Prima esecuzione — salvo baseline senza trasferire")
        save_baseline(current_equity)
        sys.exit(0)
    
    # 3. Calcola profitto giornaliero
    daily_profit = current_equity - yesterday_equity
    log.info(f"Equity ieri: {yesterday_equity:.2f} USDT")
    log.info(f"Profitto giornaliero: {daily_profit:+.2f} USDT")
    
    # 4. Trasferisci 33% se in profitto
    if daily_profit > 0:
        share_amount = daily_profit * PROFIT_SHARE_PCT
        
        # Verifica che dopo il trasferimento rimanga abbastanza capitale
        usdc_free = exchange.fetch_balance().get("free", {}).get("USDC", 0)
        if usdc_free - share_amount < SAFETY_MIN_USDC:
            log.warning(f"Saldo USDC ({usdc_free:.2f}) insufficiente per trasferire {share_amount:.2f} "
                       f"(minimo sicurezza: {SAFETY_MIN_USDC}). Trasferisco solo {usdc_free - SAFETY_MIN_USDC:.2f}")
            share_amount = max(0, usdc_free - SAFETY_MIN_USDC)
        
        if share_amount > 1.0:  # Minimo 1 USDT per trasferimento
            success = transfer_to_master(exchange, share_amount)
            if success:
                # Aggiorna baseline solo se trasferimento riuscito
                new_baseline = current_equity - share_amount
                save_baseline(new_baseline)
                log.info(f"Nuova baseline salvata: {new_baseline:.2f} USDT")
                log.info(f"💰 Profit sharing completato: {share_amount:.2f} USDT → {DESTINATION_EMAIL}")
            else:
                log.error("Profit sharing FALLITO. Baseline NON aggiornata.")
        else:
            log.info(f"Profitto troppo piccolo per trasferimento ({share_amount:.2f} USDT). Saltato.")
    else:
        log.info(f"Giornata in perdita ({daily_profit:+.2f} USDT). Nessun trasferimento.")
        # Aggiorna baseline alla nuova equity (più bassa)
        save_baseline(current_equity)
    
    log.info("Profit sharing completato.")


if __name__ == "__main__":
    main()
