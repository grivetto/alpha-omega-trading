import os
import json
import logging
import time
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Caricamento configurazioni
load_dotenv('/root/.openclaw/workspace/.env.telegram')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='/root/.openclaw/workspace/telegram_bot_interactive.log'
)
logger = logging.getLogger(__name__)

# --- Helper Functions per i Dati ---

def get_status_data(filename):
    try:
        path = f'/root/.openclaw/workspace/{filename}'
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Errore lettura {filename}: {e}")
    return None

def get_formatted_balance():
    quant = get_status_data('quant_status.json')
    grid = get_status_data('grid_status.json')
    multi = get_status_data('multi_status.json')
    
    binance_bal = quant.get('balance', 0) if quant else 0
    # Crypto.com balance spesso in grid_status o multi_status come USDT
    cdc_bal = grid.get('balance', {}).get('usdt', 0) if grid else 0
    
    # Valori stimati per asset dormienti (SHIB/ELON)
    shib_val = 4544739 * 0.00000511
    elon_val = 118000000 * 0.000000033
    dormant = shib_val + elon_val
    
    eur_total = binance_bal + (cdc_bal * 0.94) + dormant
    
    msg = (
        "💰 *BILANCIO OPERATIVO* 💰\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📊 *Capitale Totale:* `€{eur_total:.2f}`\n\n"
        f"🔸 *Binance (Fiat):* `€{binance_bal:.2f}`\n"
        f"🔹 *Crypto.com (USDT):* `${cdc_bal:.2f}`\n"
        f"💎 *Asset Dormienti:* `€{dormant:.2f}`\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🕒 _Aggiornato al: {datetime.now().strftime('%H:%M:%S')}_"
    )
    return msg

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Messaggio di benvenuto con tastiera fissa e link Dashboard"""
    keyboard = [
        ['📊 Stato Generale', '💰 Bilancio'],
        ['🎯 Segnali Quant', '🌐 Grid Engine'],
        ['📈 Web Dashboard', '🔄 Refresh']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = (
        "👋 *Ciao Sergio! Benvenuto nella plancia di comando.*\n\n"
        "Sono *Stella*, la tua assistente per il trading quantitativo. "
        "Usa i pulsanti qui sotto per monitorare i tuoi bot in tempo reale.\n\n"
        "🔗 *Dashboard Web:* https://sgrivett.ddns.net:8443/"
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '📊 Stato Generale':
        await send_general_status(update)
    elif text == '💰 Bilancio':
        await update.message.reply_text(get_formatted_balance(), parse_mode='Markdown')
    elif text == '🎯 Segnali Quant':
        await send_quant_details(update)
    elif text == '🌐 Grid Engine':
        await send_grid_details(update)
    elif text == '📈 Web Dashboard':
        msg = (
            "🚀 *DASHBOARD ONLINE*\n\n"
            "Puoi monitorare le metriche avanzate e i grafici live qui:\n"
            "🔗 https://sgrivett.ddns.net:8443/"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    elif text == '🔄 Refresh':
        await update.message.reply_text("🔄 *Aggiornamento dati in corso...*", parse_mode='Markdown')
        await update.message.reply_text(get_formatted_balance(), parse_mode='Markdown')
    else:
        await update.message.reply_text("Seleziona un'opzione dal menù qui sotto. 👇")

async def send_general_status(update: Update):
    quant = get_status_data('quant_status.json')
    grid = get_status_data('grid_status.json')
    
    q_status = "✅ RUNNING" if quant and quant.get('status') == 'running' else "❌ OFFLINE"
    g_status = "✅ RUNNING" if grid and grid.get('status') == 'RUNNING' else "❌ OFFLINE"
    
    msg = (
        "🖥 *STATO SISTEMI* 🖥\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🤖 *Quant Scalper:* {q_status}\n"
        f"⛓ *Grid Engine:* {g_status}\n"
        "📡 *Gateway:* ✅ ONLINE\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Tutti i sistemi sono monitorati e pronti all'azione."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def send_quant_details(update: Update):
    multi = get_status_data('multi_status.json')
    if not multi or 'summary' not in multi:
        await update.message.reply_text("❌ Dati Quant non disponibili al momento.")
        return
        
    summary = multi['summary']
    msg = (
        "🎯 *DETTAGLI QUANT SCALPER* 🎯\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📈 *Coppie Monitorate:* `{summary.get('total_coins', 0)}`\n"
        f"💰 *PnL Totale:* `€{summary.get('total_pnl', 0.0):.2f}`\n"
        f"🔥 *Best Trade:* `+{summary.get('best_trade', 0.0):.2f}%`\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Il bot sta operando con strategia Momentum/Mean Reversion."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def send_grid_details(update: Update):
    grid = get_status_data('grid_status.json')
    if not grid:
        await update.message.reply_text("❌ Dati Grid non disponibili.")
        return
        
    msg = (
        "🌐 *GRID ENGINE STATUS* 🌐\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💱 *Coppia:* `{grid.get('symbol', 'SOLEUR')}`\n"
        f"💵 *Prezzo:* `{grid.get('current_price', 0.0)} €`\n"
        f"📊 *Profitto Netto:* `€{grid.get('net_profit', 0.0):.4f}`\n"
        f"📦 *Ordini Eseguiti:* `{grid.get('total_trades', 0)}`\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📍 *Range:* `{grid.get('grid', {}).get('lower_bound')} - {grid.get('grid', {}).get('upper_bound')} €`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- Main ---

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN:
        print("Errore: TELEGRAM_BOT_TOKEN non trovato nel file .env.telegram")
    else:
        print("Avvio Stella Bot Interactive...")
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), main_menu_handler))
        
        app.run_polling()
