#!/usr/bin/env bash
# deploy/scripts/money_banco_secco.sh — Banco di prova a secco per Money
# Implementa docs/02_banco_di_prova_a_secco.md
# Legge saldo reale (trading + funding), calcola equity, guardia capitale, ordine dry-run, riconcilia

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/sergio/alpha-omega-trading}"
CONFIG_FILE="${CONFIG_FILE:-$PROJECT_ROOT/config/node_banco.yaml}"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/config/.env_banco}"

# Carica variabili d'ambiente
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "ERRORE: ENV_FILE '$ENV_FILE' non trovato" >&2
    exit 1
fi

# Validazione variabili richieste
for var in OKX_API_KEY OKX_API_SECRET OKX_PASSPHRASE; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERRORE: $var non impostato in $ENV_FILE" >&2
        exit 1
    fi
done

# Configurazione banco (parametri da node_banco.yaml o default)
CAPITALE_DICHIARATO="${CAPITALE_DICHIARATO:-26.0030}"  # 26 EUR bonificati sul main
FRAZIONE_PER_POSIZIONE="${FRAZIONE_PER_POSIZIONE:-0.25}"  # 25% per posizione
SYMBOL="${SYMBOL:-BTC/EUR}"
MIN_NOTIONAL="${MIN_NOTIONAL:-1.0}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EPOCH=$(date -u +%s)

log() {
    echo "[$TIMESTAMP] $*"
}

# Usa Python per la logica complessa (ccxt, calcoli)
/home/sergio/alpha-omega-trading/venv/bin/python3 <<PYEOF
import ccxt
import json
import math
import os
import sys

# Config
api_key = os.getenv('OKX_API_KEY')
api_secret = os.getenv('OKX_API_SECRET')
passphrase = os.getenv('OKX_PASSPHRASE')
hostname = os.getenv('OKX_HOSTNAME', 'eea.okx.com')

capitale_dichiarato = float(os.getenv('CAPITALE_DICHIARATO', '26.0030'))
frazione = float(os.getenv('FRAZIONE_PER_POSIZIONE', '0.25'))
symbol = os.getenv('SYMBOL', 'BTC/EUR')
min_notional = float(os.getenv('MIN_NOTIONAL', '1.0'))

timestamp = os.getenv('TIMESTAMP', '2026-01-01T00:00:00Z')
epoch = int(os.getenv('EPOCH', '0'))

log = lambda msg: print(f"[{timestamp}] {msg}", flush=True)

# CCXT exchange
ex = ccxt.okx({
    'apiKey': api_key,
    'secret': api_secret,
    'password': passphrase,
    'enableRateLimit': True,
})
ex.options['defaultType'] = 'spot'

# Forza hostname EU
if hostname != 'www.okx.com':
    ex.urls['api']['rest'] = f'https://{hostname}'

try:
    # 1. LEGGI SALDO REALE: trading E funding
    log(f"STEP 1: fetch_balance trading + funding")
    
    bal_trading = ex.fetch_balance({'type': 'trading'})
    bal_funding = ex.fetch_balance({'type': 'funding'})
    
    # Estrai EUR e altri asset con saldo > 0
    def extract_nonzero(bal, label):
        out = {}
        for ccy, data in bal.items():
            if isinstance(data, dict):
                total = float(data.get('total', 0) or 0)
                free = float(data.get('free', 0) or 0)
                if total > 0:
                    out[ccy] = {'total': total, 'free': free}
        return out
    
    trading_nz = extract_nonzero(bal_trading, 'trading')
    funding_nz = extract_nonzero(bal_funding, 'funding')
    
    log(f"  trading: {json.dumps(trading_nz, ensure_ascii=False)}")
    log(f"  funding: {json.dumps(funding_nz, ensure_ascii=False)}")
    
    # 2. CALCOLA EQUITY IN EUR (saldo EUR + valore mercato asset)
    log("STEP 2: calcolo equity in EUR")
    
    # Carica mercati per prezzi
    ex.load_markets()
    
    equity_eur = 0.0
    dettaglio = {}
    
    all_assets = {}
    for ccy, data in trading_nz.items():
        all_assets[ccy] = data
    for ccy, data in funding_nz.items():
        if ccy in all_assets:
            all_assets[ccy]['total'] += data['total']
            all_assets[ccy]['free'] += data['free']
        else:
            all_assets[ccy] = data
    
    for ccy, data in all_assets.items():
        total = data['total']
        if ccy == 'EUR':
            equity_eur += total
            dettaglio[ccy] = {'tipo': 'EUR', 'quantita': total, 'valore_eur': total}
        else:
            # Prova a ottenere prezzo EUR
            pair = f"{ccy}/EUR"
            if pair in ex.markets:
                ticker = ex.fetch_ticker(pair)
                last = float(ticker.get('last', 0) or 0)
                if last > 0:
                    valore = total * last
                    equity_eur += valore
                    dettaglio[ccy] = {'tipo': 'crypto', 'quantita': total, 'prezzo_eur': last, 'valore_eur': valore}
                else:
                    dettaglio[ccy] = {'tipo': 'crypto', 'quantita': total, 'prezzo_eur': 0, 'valore_eur': 0, 'note': 'prezzo non disponibile'}
            else:
                dettaglio[ccy] = {'tipo': 'crypto', 'quantita': total, 'prezzo_eur': 0, 'valore_eur': 0, 'note': 'pair non su OKX EEA'}
    
    log(f"  equity_eur: {equity_eur:.4f}")
    log(f"  dettaglio: {json.dumps(dettaglio, ensure_ascii=False)}")
    
    # 3. GUARDIA CAPITALE
    log("STEP 3: guardia capitale")
    
    if equity_eur >= capitale_dichiarato:
        guardia_esito = "PASS"
        log(f"  PASS: equity {equity_eur:.4f} >= capitale_dichiarato {capitale_dichiarato:.4f}")
    else:
        guardia_esito = "NON_FINANZIATO"
        diff = capitale_dichiarato - equity_eur
        log(f"  NON_FINANZIATO: equity {equity_eur:.4f} < capitale_dichiarato {capitale_dichiarato:.4f} (diff {diff:.4f})")
        # Stampa i tre numeri richiesti e esce con codice != 0
        print(f"NON_FINANZIATO equity_reale={equity_eur:.4f} capitale_dichiarato={capitale_dichiarato:.4f} differenza={diff:.4f}")
        sys.exit(2)
    
    # 4. CALCOLA ORDINE DRY-RUN
    log("STEP 4: calcolo ordine dry-run")
    
    nozionale_teorico = capitale_dichiarato * frazione
    
    # step_size e min_notional dal mercato
    market = ex.market(symbol)
    step_size = float(market.get('precision', {}).get('amount', 0.001))
    min_notional_market = float(market.get('limits', {}).get('cost', {}).get('min', min_notional))
    
    # Arrotondamento corretto: math.floor(nozionale / step) * step (NON int(step))
    if step_size > 0:
        qty = math.floor(nozionale_teorico / step_size) * step_size
    else:
        qty = 0.0
    
    nozionale_effettivo = qty * 0  # prezzo di riferimento serve, useremo last
    
    # Prezzo di riferimento
    ticker = ex.fetch_ticker(symbol)
    prezzo_rif = float(ticker.get('last', 0) or 0)
    if prezzo_rif > 0:
        nozionale_effettivo = qty * prezzo_rif
    
    log(f"  capitale_dichiarato: {capitale_dichiarato:.4f} EUR")
    log(f"  frazione_per_posizione: {frazione:.2%}")
    log(f"  nozionale_teorico: {nozionale_teorico:.4f} EUR")
    log(f"  symbol: {symbol}")
    log(f"  step_size: {step_size}")
    log(f"  min_notional (mercato): {min_notional_market:.2f} EUR")
    log(f"  qty calcolata: {qty}")
    log(f"  prezzo_rif: {prezzo_rif:.4f} EUR")
    log(f"  nozionale_effettivo: {nozionale_effettivo:.4f} EUR")
    
    # Verifica fattibilità con money.costi
    try:
        sys.path.insert(0, '/home/sergio/money_repo/src')
        from money.costi import verifica_fattibilita
        fatt = verifica_fattibilita(
            capitale=capitale_dichiarato,
            nozionale=nozionale_effettivo,
            min_notional=min_notional_market,
            frazione_massima=frazione
        )
        log(f"  fattibilita: ok={fatt.ok} motivo={fatt.motivo}")
    except Exception as e:
        log(f"  fattibilita: modulo money.costi non disponibile ({e})")
        fatt_ok = nozionale_effettivo >= min_notional_market and qty > 0
        log(f"  fattibilita (fallback): ok={fatt_ok}")
    
    # 5. STAMPA ORDINE DRY-RUN
    log("STEP 5: ordine DRY-RUN, NON INVIATO")
    
    ordine = {
        'symbol': symbol,
        'side': 'buy',  # esempio
        'type': 'market',
        'quantity': qty,
        'prezzo_riferimento_eur': prezzo_rif,
        'nozionale_eur': nozionale_effettivo,
        'pedaggio_assunto_giro_misto_pct': 0.55,  # okx_eea_spot
        'tariffa_assunta': 'okx_eea_spot',
        'etichetta': 'DRY-RUN, NON INVIATO',
        'timestamp': timestamp,
    }
    log(f"  ORDINE: {json.dumps(ordine, ensure_ascii=False)}")
    
    # 6. RICONCILIAZIONE
    log("STEP 6: riconciliazione")
    
    open_orders = ex.fetch_open_orders(symbol)
    positions = ex.fetch_positions([symbol]) if hasattr(ex, 'fetch_positions') else []
    
    log(f"  ordini_aperti: {len(open_orders)}")
    for o in open_orders:
        log(f"    {o.get('id')} {o.get('symbol')} {o.get('side')} {o.get('amount')} @ {o.get('price')}")
    
    log(f"  posizioni: {len(positions)}")
    for p in positions:
        log(f"    {p.get('symbol')} size={p.get('contracts')} side={p.get('side')} unrealized={p.get('unrealizedPnl')}")
    
    # 7. LOG METRICA (riga singola per Zabbix/aggregatore)
    log(f"METRICA banco_esito={guardia_esito} equity_eur={equity_eur:.4f} capitale_dichiarato={capitale_dichiarato:.4f} nozionale_eur={nozionale_effettivo:.4f} qty={qty} symbol={symbol} timestamp={timestamp}")

except ccxt.AuthenticationError as e:
    log(f"ERRORE AUTENTICAZIONE: {e}")
    sys.exit(3)
except ccxt.PermissionDenied as e:
    log(f"ERRORE PERMESSI (IP whitelist?): {e}")
    sys.exit(4)
except Exception as e:
    log(f"ERRORE: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

PYEOF

EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
    log "Banco terminato con exit code $EXIT_CODE"
    exit $EXIT_CODE
fi

log "Banco completato con successo"
exit 0