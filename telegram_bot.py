#!/usr/bin/env python3
import os
import json
import logging
import requests
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Carica configurazione
load_dotenv('/root/.openclaw/workspace/.env.telegram')

# Credenziali Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Endpoint API
BASE_URL = 'http://localhost:8080'
MULTI_STATUS_URL = f'{BASE_URL}/multi_status.json'

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('telegram_bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Stato profitto globale
last_profit = None

async def send_telegram(application, title, message):
    """Invia messaggio Telegram"""
    try:
        await application.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"*{title}*\n\n{message}",
            parse_mode='Markdown'
        )
        logger.info(f"Notifica inviata: {title}")
    except Exception as e:
        logger.error(f"Errore invio Telegram: {e}")

async def check_profit(context: ContextTypes.DEFAULT_TYPE):
    """Controllo periodico profitto"""
    global last_profit
    try:
        resp = requests.get(MULTI_STATUS_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            total_pnl = float(data['summary']['total_pnl'])
            
            # Notifica profitto
            if total_pnl > 0 and (last_profit is None or last_profit <= 0):
                await send_telegram(
                    context.application,
                    '💰 PROFITTO ATTIVO!',
                    f'Il bot ha iniziato a guadagnare!\n\nPnL attuale: ${total_pnl:.2f}'
                )
            elif total_pnl <= 0 and last_profit is not None and last_profit > 0:
                await send_telegram(
                    context.application,
                    '⚠️ PROFITTO AZZERATO',
                    f'Il bot ha perso i profitti accumulati.\n\nPnL attuale: ${total_pnl:.2f}'
                )
            
            last_profit = total_pnl
    except Exception as e:
        logger.error(f"Errore controllo profitto: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "🤖 Trading Bot Controller\n\n"
        "Comandi disponibili:\n"
        "/status - Stato bot\n"
        "/dashboard - Link dashboard\n"
        "/test_notif - Test notifica\n"
        "/help - Aiuto"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await start(update, context)

async def test_notif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /test_notif"""
    await send_telegram(
        context.application,
        '🧪 TEST NOTIFICA',
        'Questo è un messaggio di test dal bot controller!\nSe lo vedi, le notifiche funzionano correttamente.'
    )
    await update.message.reply_text('✅ Notifica di test inviata!')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status"""
    try:
        msg = "📊 *STATO BOT*\n\n"
        
        # --- Multi-Coin Bot ---
        try:
            with open('/root/.openclaw/workspace/multi_status.json', 'r') as f:
                multi_data = json.load(f)
                summary = multi_data.get('summary', {})
                msg += "*Multi-Coin Bot*\n"
                msg += f"├ 🪙 Crypto: {summary.get('total_coins', 0)}\n"
                msg += f"├ 🟢 BUY signals: {summary.get('buy_signals', 0)}\n"
                msg += f"├ 🔴 SELL signals: {summary.get('sell_signals', 0)}\n"
                msg += f"├ 📍 Posizioni: {summary.get('active_positions', 0)}\n"
                msg += f"├ 💰 PnL totale: ${summary.get('total_pnl', 0.0):.2f}\n"
                msg += f"└ ⚡ Win rate: {summary.get('win_rate', 0)}%\n\n"
        except Exception as e:
            msg += "*Multi-Coin Bot*\n└ ❌ Non disponibile\n\n"

        # --- Grid Trading Bot ---
        try:
            with open('/root/.openclaw/workspace/grid_status.json', 'r') as f:
                grid_data = json.load(f)
                grid_params = grid_data.get('grid', {})
                msg += "*Grid Trading Bot*\n"
                msg += f"├ 📊 Prezzo BTC: ${grid_data.get('current_price', 0):,.2f}\n"
                msg += f"├ 📈 Range: ${grid_params.get('lower_bound', 0):,.1f} - ${grid_params.get('upper_bound', 0):,.1f}\n"
                msg += f"├ 📋 Ordini attivi: {grid_data.get('active_orders', 0)}\n"
                msg += f"├ 💸 Profitto netto: ${grid_data.get('net_profit', 0.0):.4f}\n"
                msg += f"├ 🔄 Trade totali: {grid_data.get('total_trades', 0)}\n"
                status_icon = "🟢" if grid_data.get('status') == 'RUNNING' else "🔴"
                msg += f"└ {status_icon} Stato: {grid_data.get('status', 'N/A')}\n\n"
        except Exception as e:
            msg += "*Grid Trading Bot*\n└ ❌ Non disponibile\n\n"

        # --- Advanced Quant Bot ---
        try:
            if os.path.exists('/root/.openclaw/workspace/quant_status.json'):
                with open('/root/.openclaw/workspace/quant_status.json', 'r') as f:
                    quant_data = json.load(f)
                    balance = quant_data.get('balance', 0.0)
                    active_pos = sum(1 for sym, info in quant_data.get('symbols', {}).items() if info.get('position', 0) > 0)
                    msg += "*Advanced Quant Bot*\n"
                    msg += f"├ 💶 Bilancio Libero: €{balance:.2f}\n"
                    msg += f"├ 📍 Posizioni attive: {active_pos}\n"
                    msg += "└ 🟢 Stato: RUNNING\n"
        except Exception as e:
            pass

        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f'❌ Errore: {str(e)}')

async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /dashboard"""
    await update.message.reply_text(
        "🌐 *Link alle Dashboard*\n\n"
        "📊 Multi-Coin Dashboard:\nhttps://sgrivett.ddns.net:8443/\n\n"
        "📈 Grid Trading Dashboard:\nhttps://sgrivett.ddns.net:8443/grid\n\n"
        "💡 Suggerimento: aggiungi ai preferiti per un accesso rapido e sicuro (HTTPS)!",
        parse_mode='Markdown'
    )

def main():
    """Avvio bot principale"""
    # Verifica configurazione
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN non impostato!")
        return
    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID non impostato!")
        return
    
    # Inizializza bot
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Aggiungi handler
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('test_notif', test_notif))
    application.add_handler(CommandHandler('status', status_cmd))
    application.add_handler(CommandHandler('dashboard', dashboard_cmd))
    
    # Aggiungi job periodico
    application.job_queue.run_repeating(check_profit, interval=30, first=10)
    
    # Avvia bot
    logger.info("🤖 Bot Telegram avviato e in ascolto...")
    application.run_polling(allowed_updates=[])

if __name__ == '__main__':
    main()
