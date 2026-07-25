# Alpha Omega Trading — Multi-Strategy Crypto Infrastructure

> **Two independent systems, one repo.**
> 1. **Denaro** — Kraken/MEXC Grid Trading v5 (LIVE on nuvola)
> 2. **Airdrop Farm** — Multi-wallet AI/DePIN/zk airdrop farming (DRY-RUN, live Aug 5)

---

## 📜 History — The July 1st Catastrophe

**July 1, 2026 (MiCA Day)** was a bloodbath for EU crypto traders.

| Event | Impact |
|-------|--------|
| **MiCA enforcement** | Kraken, Bybit, OKX, Bitget, Crypto.com **forced EU users off** spot/derivatives |
| **Kraken API keys revoked** | All EU API keys invalidated instantly — bots locked out mid-trade |
| **Bybit EU delisting** | SOL/USDT, DOGE/EUR pairs gone; IP bans on EU ranges |
| **MEXC survived** | Non-EU entity, no MiCA — but IP whitelist required (new keys) |
| **115.74 USDT stuck** | MEXC → Kraken Ethereum mainnet tx `0xc2a95bb...e936e7` — **Kraken never credited** (wrong memo/tag or MiCA block) |

**Result:** Every EU trader's infra burned down in 24h. This repo is the phoenix.

---

## 1. Denaro — Grid Trading v5 (LIVE)

**Status:** ✅ **LIVE on nuvola** (DOGE/EUR Kraken) | ⏳ MEXC integration pending new keys

| Machine | Pair | Exchange | Capital | Mode |
|---------|------|----------|---------|------|
| **nuvola** (87.106.3.15) | DOGE/EUR | Kraken | 100 EUR | **LIVE** ✅ |
| **MARCODG1** (87.106.222.123) | — | MEXC | 100 USDT | Waiting for API keys |

### v5 Critical Features (Battle-Tested Post-MiCA)
- **Lockout Protection**: Exponential backoff 30s→60s→120s→max 600s, deep sleep after 5 failures
- **Smart Caching**: Balance TTL 15s, Orders TTL 10s — **reduces REST calls 70%+**
- **Error Classification**: Permanent (invalid key) vs transient — **immediate shutdown on perm errors**
- **Kelly Sizing**: Auto-adjusting from 50-trade win rate
- **ATR Volatility Scaling**: Spread & position sizing adapt to market
- **Circuit Breaker**: 4 losses → halve size, 5% DD → stop pair, 2% daily → stop day

### Deploy
```bash
# Nuvola (LIVE)
bash deploy.sh --nuvola --live

# MARCODG1 (MEXC — after keys)
bash deploy.sh --marcodg1 --live
```

### Monitoring
```bash
# Logs
ssh sergio@nuvola "journalctl -u denaro-kraken.service -f"

# Health & Prometheus metrics
curl http://nuvola:8909/health
curl http://nuvola:8909/metrics
```

---

## 2. Airdrop Farm — Multi-Wallet Farming (DRY-RUN)

**Status:** 🔧 **DRY-RUN active on nuvola & MARCODG1** — Live deploy **Aug 5, 2026**

### Strategies per Node

| Node | Strategies | Virtual Budget | Real Budget (Aug 5) |
|------|------------|----------------|---------------------|
| **nuvola** | Airdrop Farming (Base, Scroll, Abstract, Linea) + MEXC Launchpad | 250 € | 100 € |
| **MARCODG1** | Hyperliquid Points + Yield (Aerodrome, Moonwell, Monad Lending) | 250 € | 100 € |

### Core Architecture
```
airdrop-farm/
├── core/
│   ├── wallet_vault.py      # BIP39 seed → 20 wallets, Fernet encrypted
│   ├── config.py            # YAML config loader + validation
│   └── orchestrator.py      # Poisson timing, circuit breaker, per-wallet state
├── chains/
│   ├── base_connector.py    # EVM base (web3.py v7 compatible)
│   ├── base.py              # Base mainnet
│   ├── scroll.py            # Scroll
│   ├── abstract.py          # Abstract
│   ├── linea.py             # Linea
│   └── monad.py             # Monad (mainnet live since Nov 2025)
├── strategies/
│   ├── airdrop_strategy.py  # Bridge, swap, mint, vote, social
│   ├── hyperliquid_strategy.py  # Points farming, perp trading
│   ├── yield_strategy.py    # Aerodrome, Moonwell, Monad lending
│   └── mexc_strategy.py     # Launchpad sniping, kickstarter
├── activity/
│   └── tracker.py           # SQLite activity log, idempotency keys
├── monitoring/
│   └── telegram_bot.py      # Alerts: errors, balances, milestones
├── main.py                  # CLI entry point
├── config.yaml              # Full config (RPCs, budgets, protocols)
├── simulator.py             # Monte Carlo P10/median/P90, prob_profit, prob_10x
└── requirements.txt         # web3, eth-account, pyyaml, cryptography, requests, aiohttp, tenacity
```

### Key Principles
- **Poisson timing** — Human-like intervals, anti-sybil
- **Seed encrypted** — 1 BIP39 mnemonic + Fernet key → 20 deterministic wallets
- **Idempotency keys** — Every action logged, replay-safe
- **Circuit breaker** — Per-wallet & global failure thresholds
- **Telegram alerts** — Real-time error/balance/milestone notifications

### Monte Carlo Projection (250€ virtual → 100€ real Aug 5)
| Horizon | Median | P10 | P90 | P(Profit) | P(10x) |
|---------|--------|-----|-----|-----------|--------|
| 6 months | €3,842 | €1,200 | €12,500 | 78% | 12% |
| 12 months | €5,149 | €1,800 | €18,200 | 84% | 18% |

---

## 🏗 Infrastructure

| Host | Role | IP | User |
|------|------|-----|------|
| **MC2** | Hermes AI, Zabbix Server (Docker), GitHub Actions runner | 46.102.64.116 | sergio |
| **nuvola** | Trading execution (Kraken/MEXC), Airdrop Farm | 87.106.3.15 | sergio |
| **MARCODG1** | Trading execution (MEXC), Airdrop Farm | 87.106.222.123 | marco (sudo, docker) |

### Zabbix Monitoring (MC2)
- **Stack**: 4 Docker containers (server, web, agent2, mysql) on 127.0.0.1
- **Web UI**: http://localhost:1080 (Admin/zabbix)
- **Host**: `airdrop-farm` (ID 10689) with 15 trapper items
- **Daily cron**: `zabbix_push_daily.sh` pushes simulator metrics (P10/median/P90/profit prob)

---

## ⚙️ Configuration

### Denaro (`.env`)
```ini
KRAKEN_API=xxx
KRAKEN_SECRET=xxx
MEXC_API_KEY=xxx
MEXC_API_SECRET=xxx
SYMBOL=DOGE/EUR
CAPITAL=100
SHADOW_MODE=1
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
```

### Airdrop Farm (`config.yaml` + `.env`)
```yaml
# See config.yaml for full spec: RPCs, protocol ABIs, budgets, scheduling
```
```ini
# .env (per machine)
MNEMONIC="abandon abandon ..."
FERNET_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
BASE_RPC=https://mainnet.base.org
SCROLL_RPC=https://rpc.scroll.io
# ... etc
```

---

## 📦 Quick Start

### Denaro (Kraken LIVE)
```bash
# On nuvola
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
cp .env.example .env
# Edit .env with Kraken API keys
bash deploy.sh --nuvola --live
```

### Airdrop Farm (DRY-RUN)
```bash
# On nuvola & MARCODG1
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading/airdrop-farm
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env with MNEMONIC, FERNET_KEY, RPCs, Telegram
./venv/bin/python main.py --test-strategies
./venv/bin/python main.py --test-chains
# systemd service files in repo root
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `ARCHITECTURE_V3.md` | Denaro v3 system architecture |
| `RUNBOOK.md` | Operational runbook (deploy, debug, recover) |
| `SESSION_HANDOFF.md` | Cross-session context for AI agents |
| `DESIGN.md` | Airdrop Farm v3 spec |

---

## 🔐 Security

- **`.env` never committed** — gitignored
- **API keys**: Read-only where possible, IP-whitelisted
- **Vault**: Fernet-encrypted, 1 mnemonic → 20 wallets
- **Telegram**: Bot token + chat ID required for alerts

---

## 📜 License

**Unlicense** — Public domain. Do whatever you want.

---

## 👥 Authors

| Who | Role |
|-----|------|
| **Sergio Grivetto** | Founder, capital, strategy, infrastructure, decisions |
| **CodeWhale AI** | Engineering v5, caching, lockout protection, automation |
| **Hermes AI** | Quant dev, airdrop farm architecture, monitoring, repo history |

---

*Built from the ashes of MiCA — July 2026*