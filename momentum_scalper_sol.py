#!/usr/bin/env python3
"""
DENARO MOMENTUM SCALPER v2 — XRP scalper, SQLite persistence
Entry: EMA20 breakout + volume spike.
Exit: +0.3% profit target, -0.3% stop loss.
Max 30€ per trade, 1 posizione aperta.
"""
import os, json, time, logging, hmac, hashlib, urllib.parse, requests, sqlite3
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
BINANCE = 'https://api1.binance.com'
DB_PATH = os.path.join(BASE_DIR, '.tmp', 'denaro.db')
LOG_FILE = os.path.join(BASE_DIR, "momentum_scalper_sol.log")

handler = logging.FileHandler(LOG_FILE)
handler.setFormatter(logging.Formatter('%(asctime)s - SCALPER - %(levelname)s - %(message)s'))
logger = logging.getLogger("Scalper")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False  # Non inondare stdout/stderr

# ── CONFIG ─────────────────────────────────────────
SYMBOL = "SOLEUR"
# MAX_PER_TRADE rimosso — ora dinamico via get_trade_size()
PROFIT_TARGET = 0.010      # +1.0% (SOL più volatile, netto ~+0.75%)
STOP_LOSS = 0.005          # -0.5% (netto ~-0.75%, R:R 2:1)
CHECK_INTERVAL = 15        # secondi
MIN_VOLUME_MULT = 0.0      # Volume filter disattivato (mercato spesso piatto di notte)
SOFT_ENTRY_MULT = 0.5      # Size multiplier per soft entry
EMA_BUFFER = 0.0001        # 0.01% buffer sopra EMA20 (praticamente sopra = entry)
MIN_NOTIONAL = 5.0         # EUR — abbassato per capitale limitato (Binance minimo ~5-6€)

def sign(params):
    ts = int(time.time() * 1000)
    params['timestamp'] = ts
    query = urllib.parse.urlencode(params)
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params['signature'] = sig
    return params

def api_get(endpoint, params=None, signed=True):
    if params is None: params = {}
    p = sign(params) if signed else params
    r = requests.get(BINANCE + endpoint, params=p, headers={'X-MBX-APIKEY': API_KEY} if signed else {}, timeout=10)
    return r.json() if r.status_code == 200 else None

def api_post(endpoint, params):
    p = sign(params)
    r = requests.post(BINANCE + endpoint, params=p, headers={'X-MBX-APIKEY': API_KEY}, timeout=10)
    return r.json() if r.status_code == 200 else None

# ── TECNICI ─────────────────────────────────────────
def get_1m_data(limit=30):
    k = api_get('/api/v3/klines', {'symbol': SYMBOL, 'interval': '1m', 'limit': limit}, signed=False)
    if not k: return None, None, None
    closes = [float(x[4]) for x in k]
    volumes = [float(x[5]) for x in k]
    return closes[-1], closes, volumes

def ema(values, period=20):
    if len(values) < period: return None
    k = 2 / (period + 1)
    ema_vals = [sum(values[:period]) / period]
    for v in values[period:]:
        ema_vals.append((v - ema_vals[-1]) * k + ema_vals[-1])
    return ema_vals

# ── POSITION SIZE (dinamico dal capital pool) ─────
def get_trade_size(eur_free):
    """15% del capitale disponibile, min 8€ (adattato per capitale limitato), max 30€."""
    pool_file = os.path.join(BASE_DIR, '.tmp', 'capital_pool.json')
    try:
        with open(pool_file) as f:
            pool = json.load(f)
            available = pool.get('available_eur', eur_free)
            max_trade = pool.get('max_per_trade', 30.0)
        if available <= 0:
            available = eur_free
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        available = eur_free
        max_trade = 30.0
    size = available * 0.15
    size = max(size, 5.0)   # Abbassato a 5€ - minimo pratico per operare con capitale limitato
    size = min(size, max_trade, 30.0)
    return round(size, 2)

# ── FILTRO ORARIO ─────────────────────────────────
def should_trade():
    """Solo finestre ad alta volatilita (UTC)."""
    now = datetime.utcnow()
    hour = now.hour
    minute = now.minute
    # Asia open: 00-03 UTC
    if 0 <= hour < 3:
        return True, "ASIA"
    # EU open: 07-12 UTC (allargata per coprire overlap Londra)
    if 7 <= hour < 12:
        return True, "EU"
    # US open: 13:30-21:00 UTC (allargata per coprire tutta la sessione NY)
    if (hour == 13 and minute >= 30) or (14 <= hour < 21) or (hour == 21 and minute == 0):
        return True, "US"
    # Overlap EU/US 12-13:30 (mercato molto liquido)
    if 12 <= hour < 14:
        return True, "OVERLAP"
    # Weekend: overlap simulato 14-17
    if now.weekday() >= 5 and 14 <= hour < 17:
        return True, "WEEKEND"
    return False, None

# ── STATO (SQLite — sopravvive ai crash) ──────────
def _get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def _init_state_table():
    db = _get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS scalper_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            position_json TEXT,
            total_pnl REAL DEFAULT 0.0,
            trades INTEGER DEFAULT 0,
            updated_at TEXT
        )
    ''')
    db.commit()
    db.close()

def load_state():
    _init_state_table()
    db = _get_db()
    row = db.execute(
        'SELECT position_json, total_pnl, trades FROM scalper_state WHERE id = 1'
    ).fetchone()
    db.close()
    if row:
        pos = json.loads(row[0]) if row[0] else None
        return {'position': pos, 'total_pnl': row[1], 'trades': row[2]}
    db2 = _get_db()
    db2.execute(
        'INSERT OR IGNORE INTO scalper_state (id, position_json, total_pnl, trades, updated_at) VALUES (1, NULL, 0.0, 0, ?)',
        (datetime.now().isoformat(),)
    )
    db2.commit()
    db2.close()
    return {'position': None, 'total_pnl': 0.0, 'trades': 0}

def save_state(state):
    pos_json = json.dumps(state.get('position')) if state.get('position') else None
    db = _get_db()
    db.execute('''
        INSERT INTO scalper_state (id, position_json, total_pnl, trades, updated_at)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            position_json = excluded.position_json,
            total_pnl = excluded.total_pnl,
            trades = excluded.trades,
            updated_at = excluded.updated_at
    ''', (pos_json, state.get('total_pnl', 0.0), state.get('trades', 0),
          datetime.now().isoformat()))
    db.commit()
    db.close()

# ── MAIN ────────────────────────────────────────────
def check_position(pos, current_price):
    """Check if current position hit TP or SL — supporta BUY e SELL side"""
    entry = pos['entry_price']
    side = pos.get('side', 'BUY')
    
    if side == 'BUY':
        change = (current_price - entry) / entry
        if change >= PROFIT_TARGET:
            qty = f"{pos['qty']:.{pos.get('precision', 4)}f}"
            result = api_post('/api/v3/order', {
                'symbol': SYMBOL, 'side': 'SELL', 'type': 'MARKET', 'quantity': qty
            })
            if result and 'orderId' in result:
                profit = pos['invested'] * PROFIT_TARGET
                logger.info(f"🎯 TP LONG: venduto {pos['qty']:.4f} @ {current_price}€, profit {profit:.4f}€")
                return {'filled': 'tp', 'profit': profit, 'exit_price': current_price}
        elif change <= -STOP_LOSS:
            qty = f"{pos['qty']:.{pos.get('precision', 4)}f}"
            result = api_post('/api/v3/order', {
                'symbol': SYMBOL, 'side': 'SELL', 'type': 'MARKET', 'quantity': qty
            })
            if result and 'orderId' in result:
                loss = pos['invested'] * STOP_LOSS
                logger.info(f"🛑 SL LONG: venduto {pos['qty']:.4f} @ {current_price}€, loss {loss:.4f}€")
                return {'filled': 'sl', 'profit': -loss, 'exit_price': current_price}
    
    elif side == 'SELL':
        change = (entry - current_price) / entry
        if change >= PROFIT_TARGET:
            qty = f"{pos['qty']:.{pos.get('precision', 4)}f}"
            result = api_post('/api/v3/order', {
                'symbol': SYMBOL, 'side': 'BUY', 'type': 'MARKET', 'quantity': qty
            })
            if result and 'orderId' in result:
                profit = pos['invested'] * PROFIT_TARGET
                logger.info(f"🎯 TP SHORT: riacquistato {pos['qty']:.4f} @ {current_price}€, profit {profit:.4f}€")
                return {'filled': 'tp', 'profit': profit, 'exit_price': current_price}
        elif change <= -STOP_LOSS:
            qty = f"{pos['qty']:.{pos.get('precision', 4)}f}"
            result = api_post('/api/v3/order', {
                'symbol': SYMBOL, 'side': 'BUY', 'type': 'MARKET', 'quantity': qty
            })
            if result and 'orderId' in result:
                loss = pos['invested'] * STOP_LOSS
                logger.info(f"🛑 SL SHORT: riacquistato {pos['qty']:.4f} @ {current_price}€, loss {loss:.4f}€")
                return {'filled': 'sl', 'profit': -loss, 'exit_price': current_price}
    
    return None

def look_for_entry(current_price, closes, volumes):
    """Look for entry signal — LONG + SHORT simmetrico"""
    if len(closes) < 25 or len(volumes) < 25:
        return None, 1.0
    
    ema_vals = ema(closes, 20)
    if not ema_vals: return None, 1.0
    
    ema20 = ema_vals[-1]
    avg_vol = sum(volumes[-20:-5]) / 15 if len(volumes) >= 20 else sum(volumes) / len(volumes)
    
    price_above_ema = current_price > ema20 * (1 + EMA_BUFFER)
    price_below_ema = current_price < ema20 * (1 - EMA_BUFFER)
    price_near_ema = abs(current_price - ema20) / ema20 < 0.002
    vol_ok = volumes[-1] > avg_vol * MIN_VOLUME_MULT
    upward = closes[-1] > closes[-2] if len(closes) >= 2 else False
    downward = closes[-1] < closes[-2] if len(closes) >= 2 else False
    turning_up = (closes[-1] > closes[-2]) and (closes[-2] > closes[-3]) if len(closes) >= 3 else False
    turning_down = (closes[-1] < closes[-2]) and (closes[-2] < closes[-3]) if len(closes) >= 3 else False
    
    # === LONG SIGNALS ===
    if price_above_ema and vol_ok and upward:
        logger.info(f"⚡ BUY: {current_price:.4f} > EMA20 {ema20:.4f}, vol ok, upward")
        return 'BUY', 1.0
    
    if price_near_ema and vol_ok and upward:
        logger.info(f"🟡 Soft BUY: {current_price:.4f} ~ EMA20 {ema20:.4f}")
        return 'BUY', SOFT_ENTRY_MULT
    
    if current_price < ema20 and turning_up and vol_ok:
        logger.info(f"🔄 MR BUY: {current_price:.4f} < EMA20 {ema20:.4f} ma risalendo")
        return 'BUY', SOFT_ENTRY_MULT * 0.5
    
    # === SHORT SIGNALS ===
    if price_below_ema and vol_ok and downward:
        logger.info(f"⚡ SELL SHORT: {current_price:.4f} < EMA20 {ema20:.4f}, vol ok, downward")
        return 'SELL', 1.0
    
    if price_near_ema and vol_ok and downward:
        logger.info(f"🟠 Soft SELL: {current_price:.4f} ~ EMA20 {ema20:.4f}")
        return 'SELL', SOFT_ENTRY_MULT
    
    if current_price > ema20 and turning_down and vol_ok:
        logger.info(f"🔄 MR SELL: {current_price:.4f} > EMA20 {ema20:.4f} ma scendendo")
        return 'SELL', SOFT_ENTRY_MULT * 0.5
    
    return None, 1.0

def main():
    logger.info("=" * 50)
    logger.info("MOMENTUM SCALPER AVVIATO")
    state = load_state()

    # 0. SEMPRE: check posizione aperta per TP/SL (anche fuori orario)
    pos = state.get('position')
    if pos:
        current_price, _, _ = get_1m_data()
        if current_price:
            result = check_position(pos, current_price)
            if result:
                state['total_pnl'] += result['profit']
                state['trades'] += 1
                state['position'] = None
                save_state(state)
                logger.info(f"📊 PnL totale: {state['total_pnl']:.4f}€ ({state['trades']} trade)")
                return
        else:
            # Recovery: verifica che la posizione esista ancora su Binance
            bal = api_get('/api/v3/account')
            if bal and 'balances' in bal:
                asset = pos.get('symbol', SYMBOL).replace('EUR', '')
                try:
                    held = float([b for b in bal['balances'] if b['asset'] == asset][0]['free'])
                except (IndexError, KeyError):
                    held = 0.0
                if held < pos.get('qty', 0) * 0.5:
                    logger.warning(f"🔧 RECOVERY: posizione {pos.get('qty', 0):.4f} {asset} non trovata (exchange ha {held:.4f}). Ripristino.")
                    state['position'] = None
                    state['total_pnl'] -= pos.get('invested', 0) * 0.01
                    save_state(state)

    # 1. Filtro orario — SOLO per nuovi entry
    trade_ok, slot = should_trade()
    if not trade_ok:
        logger.info(f"🕐 Fuori orario ({slot}) — skip ciclo")
        return

    current_price, closes, volumes = get_1m_data()
    if not current_price:
        logger.warning("Impossibile ottenere dati di mercato")
        return

    # 2. Look for entry (only if no position open and in trading hours)
    pos = state.get('position')
    if not pos:
        bal = api_get('/api/v3/account')
        if not bal:
            logger.warning("Fallita lettura saldo — API key problem?")
            return

        signal, size_mult = look_for_entry(current_price, closes, volumes)
        if not signal:
            ema20_vals = ema(closes, 20)
            ema20_str = f"{ema20_vals[-1]:.4f}" if ema20_vals else "N/A"
            logger.info(f"Nessun segnale: prezzo={current_price}, EMA20={ema20_str}")
            return

        asset = SYMBOL.replace('EUR', '')
        qty = 0.0

        if signal == 'BUY':
            try:
                eur_free = float([b for b in bal['balances'] if b['asset'] == 'EUR'][0]['free'])
            except (IndexError, KeyError, TypeError):
                logger.warning("Saldo EUR non trovato")
                return
            trade_size = get_trade_size(eur_free)
            if eur_free < trade_size:
                logger.info(f"EUR insufficiente: {eur_free:.2f}€ (servono {trade_size:.2f}€)")
                return
            invest = max(trade_size * size_mult, MIN_NOTIONAL)
            qty = invest / current_price

        elif signal == 'SELL':
            try:
                asset_free = float([b for b in bal['balances'] if b['asset'] == asset][0]['free'])
            except (IndexError, KeyError, TypeError):
                logger.info(f"Asset {asset} non disponibile per SELL — skip")
                return
            max_sell_qty = asset_free * 0.5
            max_sell_value = max_sell_qty * current_price
            invest = max(max_sell_value * size_mult, MIN_NOTIONAL)
            qty = invest / current_price
            if qty > max_sell_qty:
                qty = max_sell_qty
            if qty * current_price < MIN_NOTIONAL:
                logger.info(f"Valore SELL troppo basso: {qty * current_price:.2f}€ < {MIN_NOTIONAL}€")
                return

        notional = qty * current_price
        if notional < MIN_NOTIONAL:
            logger.warning(f"Notional {notional:.2f}€ < {MIN_NOTIONAL}€ minimo — entry saltata")
            return

        info = api_get('/api/v3/exchangeInfo', {'symbol': SYMBOL}, signed=False)
        step_size = 0.0001
        if info and info.get('symbols'):
            for f in info['symbols'][0]['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    break
        step_str = str(step_size)
        decimals = abs(step_str.find('1') - step_str.find('.') - 1) if '.' in step_str else 4
        qty_rounded = int(qty / step_size) * step_size

        result = api_post('/api/v3/order', {
            'symbol': SYMBOL, 'side': signal, 'type': 'MARKET',
            'quantity': f"{qty_rounded:.{decimals}f}"
        })

        if result and 'orderId' in result:
            filled_qty = float(result.get('executedQty', qty_rounded))
            filled_cost = float(result.get('cummulativeQuoteQty', qty_rounded * current_price))
            pos_data = {
                'symbol': SYMBOL,
                'entry_price': current_price,
                'qty': filled_qty,
                'invested': filled_cost,
                'precision': decimals,
                'side': signal,
                'time': datetime.now().isoformat()
            }
            state['position'] = pos_data
            save_state(state)
            emoji = '🟢' if signal == 'BUY' else '🔴'
            logger.info(f"{emoji} ENTRY {signal}: {filled_qty:.{decimals}f} {asset} @ {current_price:.4f}€ ({filled_cost:.2f}€)")
            if signal == 'BUY':
                logger.info(f"   TP @ {current_price * (1+PROFIT_TARGET):.4f}€, SL @ {current_price * (1-STOP_LOSS):.4f}€")
            else:
                logger.info(f"   TP @ {current_price * (1-PROFIT_TARGET):.4f}€, SL @ {current_price * (1+STOP_LOSS):.4f}€")

if __name__ == '__main__':
    _init_state_table()
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Errore: {e}")
        time.sleep(CHECK_INTERVAL)
