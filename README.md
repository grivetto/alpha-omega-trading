# Alpha Omega Trading — Multi-Strategy Crypto Infrastructure

> **Two independent systems, one repo.**
> 1. **Denaro** — Kraken/Bybit Grid Trading v5 (LIVE on nuvola)
> 2. **Airdrop Farm** — Multi-wallet AI/DePIN/zk airdrop farming (DRY-RUN, live Aug 5)

---

## 1. Denaro — Grid Trading v5 (LIVE)

**Status:** ✅ **LIVE on nuvola** (DOGE/EUR Kraken) | SHADOW on MARCODG1 (SOL/USDT Bybit — invalid key)

| Machine | Pair | Exchange | Capital | Mode |
|---------|------|----------|---------|------|
| **nuvola** | DOGE/EUR | Kraken | 100 EUR | **LIVE** ✅ |
| **MARCODG1** | SOL/USDT | Bybit | 100 USDT | SHADOW (key invalid) |

### v5 Critical Features
- **Lockout Protection**: Exponential backoff 30s→60s→120s→max 600s, deep sleep after 5 failures
- **Smart Caching**: Balance TTL 15s, Orders TTL 10s — reduces REST calls 70%+
- **Error Classification**: Permanent (invalid key) vs transient — immediate shutdown on perm errors
- **Kelly Sizing**: Auto-adjusting from 50-trade win rate
- **ATR Volatility Scaling**: Spread & position sizing adapt to market
- **Circuit Breaker**: 4 losses → halve size, 5% DD → stop pair, 2% daily → stop day

### Deploy
```bash
# Nuvola (LIVE)
bash deploy.sh --nuvola --live

# MARCODG1 (via jump host)
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

## 2. Airdrop Farm — Multi-Wallet Airdrop/Points/Yield (DRY-RUN)

**Status:** 🔧 **DRY-RUN active on nuvola & MARCODG1** — Live deploy **Aug 5, 2026**

### Strategies per Node

| Node | Strategies | Budget (Virtual) | Budget (Real, Aug 5) |
|------|------------|------------------|---------------------|
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
│   ├── monad.py             # Monad (mainnet since Nov 2025)
│   └── hyperliquid.py       # Hyperliquid L1 API
├── strategies/
│   ├── airdrop_strategy.py  # Domain mint, NFT mint, referral, LP
│   ├── mexc_strategy.py     # Hold MX, auto-join launchpad
│   ├── hyperliquid_strategy.py  # Perp/Spot volume for points
│   └── yield_strategy.py    # Aerodrome, Moonwell, Velocore, Monad lending
├── activity/
│   └── tracker.py           # SQLite idempotency, nonce mgmt, gas tracking
├── monitoring/
│   ├── telegram_bot.py      # Alerts + daily summary
│   └── zabbix_push.py       # Trapper items → MC2 Zabbix
└── main.py                  # CLI entry (--dry-run, --test-strategies, --test-chains)
```

### Key Principles
- **Poisson Timing**: 6–48h random intervals per wallet (anti-sybil)
- **Seed Encryption**: Single BIP39 mnemonic → 20 derived wallets, Fernet encrypted
- **Idempotency**: SQLite tracker prevents duplicate actions
- **Circuit Breaker**: 5% daily loss / 10 failures → 24h cooldown
- **Telegram Alerts**: Start/stop, errors, daily P&L
- **Zabbix Monitoring**: Monte Carlo simulation metrics (P10/P50/P90, prob_profit, prob_10x)

### Config (per node)
```bash
# nuvola
scp config.nuvola.yaml nuvola:/home/sergio/airdrop-farm/config.yaml

# MARCODG1
scp config.MARCODG1.yaml MARCODG1:/home/marco/airdrop-farm/config.yaml
```

### Run (DRY-RUN)
```bash
# On each node
cd /home/sergio/airdrop-farm  # or /home/marco/airdrop-farm
./venv/bin/python main.py --dry-run --num-wallets 5
```

### Test Commands
```bash
./venv/bin/python main.py --test-strategies  # Verify all strategies execute
./venv/bin/python main.py --test-chains      # Verify RPC connectivity
```

### Go Live (Aug 5)
1. Fund wallets from vault (run `wallet_vault.py` to derive addresses)
2. Add API keys to `.env` (MEXC, Bybit, RPC endpoints)
3. Set `dry_run: false` in config.yaml
4. Start via systemd (service files TODO)

---

## Repository Structure

```
alpha-omega-trading/
├── denaro/                    # Grid Trading v5 (LIVE)
│   ├── main.py               # KrakenBot v5
│   ├── denaro_core.py        # Core engine
│   ├── kraken_engine.py      # Kraken WS+REST
│   ├── bybit_engine.py       # Bybit WS+REST
│   ├── notifier.py           # Telegram alerts
│   ├── deploy.sh             # Deploy script
│   └── ...
├── airdrop-farm/             # Airdrop/Points/Yield (DRY-RUN)
│   ├── core/
│   ├── chains/
│   ├── strategies/
│   ├── activity/
│   ├── monitoring/
│   ├── config.nuvola.yaml
│   ├── config.MARCODG1.yaml
│   ├── main.py
│   └── requirements.txt
├── README.md                 # This file
├── LICENSE                   # Unlicense (public domain)
└── .gitignore
```

---

## Authors

| Role | Name |
|------|------|
| **Founder, Capital, Strategy, Infra, Decisions** | Sergio Grivetto |
| **AI Engineering (v5, airdrop-farm, caching, lockout, architecture)** | Hermes AI (Nous Research) |

---

## License

**Unlicense** — Public domain. Do whatever you want.

---

*Last updated: July 24, 2026 — Airdrop Farm deployed to nuvola & MARCODG1 in DRY-RUN*