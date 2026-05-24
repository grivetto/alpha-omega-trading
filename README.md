# Denaro — Multi-Node Adaptive Crypto Trading System

[![Status](https://img.shields.io/badge/status-production-green)]()
[![Exchange](https://img.shields.io/badge/exchange-Binance-F0B90B)]()
[![Python](https://img.shields.io/badge/python-3.14-blue)]()

**Denaro** is a distributed multi-strategy trading system that runs across three independent nodes, each executing a distinct algorithmic strategy on Binance spot markets. Each node operates its own Binance sub-account, eliminating balance contention and allowing parallel execution.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Denaro Trading System                     │
├──────────────┬──────────────────┬───────────────────────────┤
│   Nuvola     │      Mc2         │        MARCODG1           │
│  SOL/EUR     │  28 USDT Pairs   │       ADA/EUR             │
│ Regime Grid  │ Momentum Scalper │     Trend Grid            │
└──────┬───────┴────────┬─────────┴─────────────┬─────────────┘
       │                │                       │
       └────────────────┼───────────────────────┘
                        │
                  ┌─────▼──────┐
                  │   Binance   │
                  │  Spot APIs  │
                  └─────▲──────┘
                        │
              ┌─────────┴─────────┐
              │    Zabbix         │
              │   Monitoring      │
              └───────────────────┘
```

Each node runs **one focused bot** with its own `.env` credentials (Binance sub-account), its own config, and its own strategy. BNB balances are maintained on each sub-account for fee discount.

---

## Node Strategies

### Nuvola — Regime-Adaptive Grid (SOL/EUR)

Uses **regime detection** (inspired by Hidden Markov Model principles) to classify market conditions into 4 states and adjust grid parameters dynamically:

| Regime | Grid Levels | Spacing | Profit Target | Risk |
|--------|-------------|---------|---------------|------|
| Bull   | 6           | 1.5%    | 0.4%          | Aggressive |
| Bear   | 2           | 2.5%    | 0.6%          | Defensive |
| Choppy | 4           | 0.8%    | 0.3%          | Mean-reversion |
| Volatile | 3         | 3.0%    | 0.8%          | Wide buffer |

**Regime detection** combines:
- EMA50/EMA200 cross (trend direction & strength)
- ATR (volatility regime)
- RSI (momentum confirmation)
- Volume ratio (participation)

**Kill switches:**
- Portfolio floor: 45 EUR
- Max drawdown: 8%
- Out-of-bounds price protection

---

### Mc2 — Momentum Multi-Pair Scalper (28 USDT Pairs)

Multi-pair momentum strategy scanning 28 altcoin pairs for oversold bounces with volume confirmation:

**Entry conditions (all must be true):**
1. RSI(14) < 30 (oversold)
2. Price > EMA50 (trend alignment)
3. Volume > 1.5× 20-period average (institutional interest)
4. ATR > 0 (liquid market)

**Risk management:**
- TP: ATR × 1.5 (limit order)
- SL: ATR × 2.0 (limit order)
- Max 3 concurrent positions
- Position size: risk-based (1% of 500 USDT capital per trade)
- Max 33 USDT per position

**Tracked pairs:** MATIC, MKR, UNI, ALGO, CHZ, FTM, GALA, BCH, ADA, LINK, ETC, AVAX, NEAR, XTZ, VET, AAVE, DOT, SAND, MANA, FIL, XLM, ENJ, ZIL, BAT, EOS, LTC, AXS, ATOM

---

### MARCODG1 — Trend Grid + Auto-Switch (ADA/EUR)

Grid trading with trend filter and automatic pair switching:

**Primary:** ADA/EUR grid with regime-adjusted parameters
**Backup:** SOL/EUR (auto-switches if ADA volatility < 0.5%)

**Regime detection** adjusts grid levels, spacing, and investment limits based on market conditions.

**Auto-switch logic:**
- If ADA/EUR hourly ATR < 0.5% for 4+ hours → switch to SOL/EUR
- Switches back when ADA volatility recovers above threshold
- 4-hour cooldown between switches

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.14 |
| Exchange API | CCXT 4.5.x |
| Data Analysis | pandas, pandas-ta |
| Streams | WebSocket (real-time ticker) |
| Fee Discount | BNB (set as default fee currency) |
| Monitoring | Zabbix agent + custom metrics |
| Deployment | systemd services |
| Distribution | 3 independent nodes |

---

## Repository Structure

```
denaro/
├── .env                  # Per-node Binance API keys + Telegram
├── denaro_shared.py      # Shared library (client, regime detector, state, alerts)
├── nuvola_bot.py         # Nuvola: SOL/EUR regime grid
├── mc2_bot.py            # Mc2: 28-pair momentum scalper
├── marcodg1_bot.py       # MARCODG1: ADA/EUR trend grid + auto-switch
├── config_nuvola.json    # Nuvola configuration
├── config_mc2.json       # Mc2 configuration
├── config_marcodg1.json  # MARCODG1 configuration
├── zabbix_nuvola.conf    # Zabbix agent config — Nuvola
├── zabbix_mc2.conf       # Zabbix agent config — Mc2
├── zabbix_marcodg1.conf  # Zabbix agent config — MARCODG1
├── zabbix_nuvola_metric.py
├── zabbix_mc2_metric.py
├── zabbix_marcodg1_metric.py
└── README.md
```

---

## Deployment

```bash
# Each node (run locally on each machine):
git pull origin Prod-V2
cd /home/{user}/denaro
python3 -m venv venv
source venv/bin/activate
pip install ccxt pandas pandas-ta websockets python-dotenv
cp .env.example .env   # Edit with Binance sub-account keys

# Run:
screen -dmS denaro bash -c "cd /home/{user}/denaro && venv/bin/python3 {node}_bot.py"

# Or systemd:
cp {node}_bot.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable {node}_bot && systemctl start {node}_bot
```

---

## Monitoring

Zabbix metrics available on each node:
- `denaro.bot.status` — Bot alive check
- `denaro.metrics` — JSON with price, balance, PnL, trades, regime
- `denaro.bot.alive` — Process count
- `denaro.load.1m`, `denaro.mem.pct`, `denaro.disk.pct` — System health

---

## License

MIT
