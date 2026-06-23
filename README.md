# Alpha Omega Trading — Denaro

> **Production-grade automated crypto trading on Binance**  
> Multi-agent, regime-aware, self-optimising. H24/7.

[![GitHub](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen)]()

---

## 📐 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    DENARO TRADING SYSTEM                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  🤖 MC2 (15GB, Intel N150)           🖥️ Nuvola (4GB)       │
│  ├── Grid Bot (SOL/USDC)             ├── Stella Grid        │
│  ├── Arbitrage Bot                    │   (WebSocket, SOL)  │
│  ├── Gariban Beggar (micro-scalper)   └── API Gateway        │
│  ├── Portfolio Allocator                                   │
│  └── LLM Strategy Optimizer           🖥️ MARCODG1 (4GB)    │
│                                        ├── Grid Bot         │
│  📡 Binance API                        │   (ADA/USDC)       │
│  🧠 Ollama qwen3.5 (local via LAN)     └── API Gateway      │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  📊 Performance    |    🛡️ Risk Management                 │
│  • Sharpe > 1.0    |    • Max daily drawdown 3%             │
│  • WinRate > 45%   |    • Consecutive losses circuit-breaker │
│  • Kelly sizing    |    • Monte Carlo VaR (95% confidence)   │
│  • Regime-aware    |    • Multi-level kill-switch            │
├──────────────────────────────────────────────────────────────┤
│  💰 Capital: 3 sub-accounts ($196 deployed + $24 MAIN)       │
│  📈 Profit sharing: sergio@grivetto.eu 33% daily @23:50 UTC │
└──────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/grivetto/alpha-omega-trading
cd alpha-omega-trading
pip install requests pydantic duckdb ccxt

# Configure
cp .env.master .env
# Edit .env with your Binance API keys

# Run
python consolidation_bot.py        # Main production bot (SOL/USDC)
python gariban_beggar.py           # Micro-scalper
python services/dashboard.py       # Web dashboard
```

## 📋 Services (systemd)

| Service | Machine | Symbol | Status |
|---------|---------|--------|--------|
| `denaro-mc2-grid` | MC2 | SOL/USDC | 🟢 Grid 4 livelli |
| `denaro-mc2-arb` | MC2 | SOL/BTC/USDC | 🟢 Triangolare |
| `denaro-gariban` | MC2 | SOL/USDC | 🟢 Micro-scalper V2 |
| `denaro-v2` | MC2 | Multi | 🟢 LLM + EW + Portfolio |
| `denaro-nuvola-stella` | Nuvola | SOL/USDC | 🟢 WebSocket Grid |
| `denaro-marcodg1-grid` | MARCODG1 | ADA/USDC | 🟢 Grid ADA |

## 🧠 Strategies

### Grid Market Making
Regime-aware grid deployment. Adapts spacing and levels based on volatility regime (quiet/ranging/volatile/trending). No martingale — fixed size per level.

### Gariban Beggar (Micro-Scalper)
Entry at -0.8% dip, target +0.4%, stop-loss -2%. High-frequency small profits that compound over hundreds of cycles.

### LLM Strategy Optimizer
Local Ollama (qwen3.5:4b) analyses RSI, order book imbalance, spread, and volatility every 180s. Suggests grid parameter adjustments — never blocks trades.

### Portfolio Allocator (3-strategy)
- **Grid** (40%) — Market making on SOL/USDC
- **Mean Reversion RSI** (30%) — RSI < 25 buy, > 60 sell
- **Momentum Trend** (30%) — EMA 8/21 cross with volume filter  
Daily Kelly-based rebalancing. Max €5 per trade.

## 🛡️ Risk Management

- **Level 1**: 3 consecutive losses → block new entries
- **Level 2**: Daily loss > 3% → block + reduce size 50%
- **Level 3**: Daily loss > 5% → liquidate ALL positions + halt
- **Level 4**: Monte Carlo VaR(95%) > 4% equity → reduce size 50%
- Half-Kelly fraction on all position sizing
- BNB ≥ 0.002 checked at startup (fee discount)

## 📊 Observability

```
/health  → {"equity": 197.50, "regime": "ranging", "risk_status": "ok", ...}
/metrics → Prometheus-style counters
```

## 🗂️ Project Structure

```
├── consolidation_bot.py    # Main production entry point
├── gariban_beggar.py       # Micro-scalper with kill-switch
├── mc2_bot.py              # MC2 dedicated bot
├── arb_bot.py              # Triangular arbitrage
├── stella_grid.py          # WebSocket grid for Nuvola
├── main.py                 # Legacy main (MARCODG1)
├── core/                   # Engine, risk, portfolio, settings
├── risk_modules/           # AdvancedRiskManager, analytics
├── services/               # Dashboard, early_warning, portfolio_optimizer
├── strategies/             # Grid, dynamic_grid, scalper
├── config/                 # JSON configs per bot
├── scripts/                # Backtest gate, nightly evolution
├── tools/                  # ATR calculator, profit sharing
└── templates/              # Dashboard HTML
```

## ⚙️ Configuration

```bash
# .env — Required variables
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
GRID_CAPITAL_USDC=70
TOTAL_CAPITAL_USDC=200
DRY_RUN=false
GRID_LEVELS=4
GRID_SPACING_PCT=0.012
MAX_DAILY_LOSS_PCT=3.0
```

## 📈 Performance Requirements

| Metric | Target |
|--------|--------|
| Sharpe Ratio | > 1.0 |
| Max Drawdown (daily) | < 3% |
| Win Rate | > 45% |
| Kelly Fraction | 0.5 (Half-Kelly) |
| Min BNB balance | 0.002 |

---

*Hermes AI — Autonomous Trading Agent v2. June 2026.*
