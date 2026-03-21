# Trading Bot Binance - Guida Rapida

## 📁 File di Configurazione
**Percorso file chiavi API:**
```
/root/.openclaw/workspace/.env
```

## ✏️ Come Inserire le Chiavi
1. Apri il file `.env`
2. Sostituisci `INSERISCI_QUI_LA_TUA_API_KEY` con la tua API Key
3. Sostituisci `INSERISCI_QUI_LA_TUA_SECRET_KEY` con la tua Secret Key

## 🚀 Come Avviare il Bot
```bash
# Modalità 1: Usando lo script
cd /root/.openclaw/workspace
./run_bot.sh

# Modalità 2: Manualmente
cd /root/.openclaw/workspace
source trading_bot_env/bin/activate
python binance_trading_bot.py
```

## 📊 Modalità Default
- **PAPER_TRADING = True** (test con soldi virtuali)
- **Symbol:** BTCUSDT
- **Timeframe:** 15 minuti

## ⚙️ Per Trading Reale
Modifica nel file `binance_trading_bot.py`:
```python
PAPER_TRADING = False  # Cambia da True a False
```

## 📝 Log
I log vengono salvati in:
```
/root/.openclaw/workspace/trading_bot.log
```

---

## 🔧 Daemon Systemd (Avvio Automatico)

Il bot è configurato come servizio che parte automaticamente al riavvio del server.

### Gestione Rapida:
```bash
cd /root/.openclaw/workspace

# Avvia il bot
./bot_ctl.sh start

# Ferma il bot
./bot_ctl.sh stop

# Riavvia il bot
./bot_ctl.sh restart

# Controlla lo stato
./bot_ctl.sh status

# Visualizza log in tempo reale
./bot_ctl.sh logs
```

### Comandi Systemd Diretti:
```bash
systemctl start binance-bot      # Avvia
systemctl stop binance-bot       # Ferma
systemctl restart binance-bot    # Riavvia
systemctl status binance-bot     # Stato
journalctl -u binance-bot -f     # Log live
```

> **Nota:** Il servizio è già abilitato e partirà automaticamente dopo ogni riavvio del server.
