# Binance Pro Trading Bot Infrastructure

## 🚀 Avanzamento Lavori & Architettura (Live)

Questa repository contiene l'infrastruttura completa del sistema di trading automatizzato, configurato per operare in reale sul mercato **Spot di Binance** con un micro-capitale (adattato per EUR, target 24€).

### 🤖 Componenti Attivi

1. **Advanced Quant Bot (`advanced_quant_bot.py`)**
   - **Ruolo**: Cecchino ad alta frequenza (Scalper).
   - **Target**: `BTCEUR`, `ETHEUR`, `SOLEUR`, `BNBEUR`
   - **Timeframe**: 3 minuti
   - **Indicatori**: RSI (<40), Breakout Bande di Bollinger (deviazione 1.8), Spike di Volume (1.3x).
   - **Risk Management**: Capitale fisso di 5.5€ a trade, Trailing Stop-Loss aggressivo all'1.0%, Take Profit rapido al +2.0%.
   - **Stato**: In esecuzione continua (`quant-bot.service`).

2. **Grid Trading Bot (`binance_grid_bot.py`)**
   - **Ruolo**: Compra e vendi sui ritracciamenti per incassare la volatilità orizzontale.
   - **Target**: `SOLEUR` (Solana)
   - **Parametri Griglia**: 4 livelli (da 70€ a 84€), allocazione statica di 6€ per livello per rispettare i requisiti `NOTIONAL` minimi di Binance (5€).
   - **Stato**: In esecuzione continua (`binance-grid-bot.service`).

3. **Telegram Controller (`telegram_bot.py`)**
   - **Ruolo**: Centro di comando mobile e sistema di notifica.
   - **Features**: Visualizza un resoconto istantaneo e formattato del PnL, segnali aperti, stato della griglia, bilanci tramite `/status`. Fornisce scorciatoie per la web dashboard tramite `/dashboard`.
   - **Stato**: In esecuzione continua (`telegram-bot.service`).

### 🌐 Infrastruttura Web (HTTPS / Reverse Proxy)
Il server espone le metriche in modo sicuro usando Apache2 e Let's Encrypt (Certbot):
- **OpenClaw UI**: `https://sgrivett.ddns.net` (Porta 443)
- **Multi-Coin Dashboard**: `https://sgrivett.ddns.net:8443` (Porta 8443)
- **Grid Dashboard**: `https://sgrivett.ddns.net:8443/grid`

### ⚙️ Installazione & Dipendenze
Tutto l'ambiente è isolato virtualmente per mantenere l'host pulito.
Le dipendenze chiave (situate in `trading_bot_env`):
- `python-binance` (API Exchange)
- `pandas` e `pandas_ta` (Indicatori e data manipulation)
- `python-telegram-bot` con `job-queue` (Controller bot)
- `ccxt` (Aggiunto per future integrazioni cross-exchange, es. Crypto.com)

*Note: The `.env` file containing API keys is strictly ignored in git to ensure maximum security.*
