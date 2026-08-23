<div align="center">

# ⚡ ALPHA-OMEGA TRADING ⚡

### *ระบบเทรดอัลกอริทึมแบบกระจายอำนาจสูงสุด — จากกระดาษสู่กำไรข้ามสองโหนด โดยไม่มีการถอยหา* 

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CCXT](https://img.shields.io/badge/exchange-CCXT%20Pro%20%2F%20Kraken%20%7C%20OKX-5741D9?logo=bitcoin&logoColor=white)](https://github.com/ccxt/ccxt)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20systemd%20%7C%20Docker-FCC624?logo=linux&logoColor=black)](https://www.freedesktop.org/wiki/Software/systemd/)
[![Status](https://img.shields.io/badge/status-LIVE%20%E2%82%AC50%20CAPITAL%20%7C%2012%20BOTS%20OPERATIONAL-brightgreen)](https://github.com/grivetto/alpha-omega-trading)
[![Architecture](https://img.shields.io/badge/architecture-distributed%2C%20async%2C%20fleet%20orchestrated-brightgreen)]()
[![Monitoring](https://img.shields.io/badge/monitoring-Zabbix%20%2B%20Grafana%20%2B%20Telegram-FF6F00?logo=grafana&logoColor=white)]()

**ฝูงหุ่นยนต์เทรดหลายกลยุทธ์แบบ async แบบกระจายข้ามสองเครื่อง ข้อมูลตลาดเรียลไทม์ผ่าน ZeroMQ สถานะร่วมผ่าน Redis Streams จัดการความเสี่ยงพอร์ตโฟลิโอ เลือกคู่เงินไดนามิก — ผ่านการตรวจสอบกระดาษแล้ว พร้อมไปไลฟ์**

[Architecture](#-architecture) · [Philosophy](#-philosophy) · [Quick Start](#-quick-start) · [Deployment](#-deployment) · [Monitoring](#-monitoring--observability) · [Roadmap](#-roadmap)

</div>

---

## 🚀 GO-LIVE: 2026-08-10 22:42:30 CEST — €50 REAL CAPITAL DEPLOYED (สถาปัตยกรรม v2.3 Split-by-Exchange)

> **GO-LIVE ยืนยันแล้ว** — ระบบทำงานจริงด้วยทุนจริง สถาปัตยกรรม split-by-exchange: ไม่มีการชนกันของบัญชี

| Exchange | บัญชี | ทุน | โหนด | บอท | คู่เงิน |
|----------|--------|------|------|-----|---------|
| **Kraken** | ร่วม | €25.50 EUR | Nuvola | 6 | ADA, DOGE, ETH, LINK, SOL, XRP |
| **OKX (EEA)** | ร่วม | €25.00 EUR | MARCODG1 | 6 | ADA, BICO, DOGE, GRVT, LINK, XRP |
| **รวม** | — | **€50** | 2 | **12** | 12 คู่เงินที่ไม่ซ้ำ |

**Risk Limits Armed (ต่อ exchange):**
- Max DD ต่อบอท: 15% (€1.04)
- ขีดจำกัดขาดทุนรายวัน: 5% (€1.25)
- Kill switch พอร์ตโฟลิโอ: 20% (€5)
- Correlation filter: 0.7
- Max 2 positions ต่อ base currency

**Monitoring:**
- ✅ Zabbix บน mc2 (ตรวจสอบทุกนาที)
- ✅ Health API :8900 ต่อโหนด

---

## 🎯 Philosophy (ปรัชญา)

> **การปกป้องทุนคือกฎหมาย ประสิทธิภาพคือกำไร โค้ดคือกฎหมาย กำไรคือหลักฐาน การกระจายอำนาจคือความทนทาน**

Alpha-Omega Trading เกิดจากข้อจำกัดง่ายๆ: **ทุนจำกัดต้องไม่ถูกเสี่ยง — ต้องได้รับการเพาะเลี้ยงข้ามโครงสร้างพื้นฐานแบบกระจายที่ทนทาน**

ทุกการตัดสินใจด้านการออกแบบปฏิบัติตาม 4 กฎ:

1. **🛡️ อย่ามีความเสี่ยงมากกว่าที่คุณจะสูญเสียได้** — circuit breaker, ขีดจำกัด drawdown, position cap, และ correlation limit ไม่ใช่ฟีเจอร์เสริม; มันคือรากฐานที่ทุกระดับ (บอท, พอร์ตโฟลิโอ, ฝูง)
2. **⚙️ อย่าเสียทรัพยากร** — ไม่มี framework ที่บวม, ไม่มีกระบวนการซ้ำซ้อน, ไม่มีบริการที่ถูกทิ้งทอดบริโภค RAM Async I/O, circular buffers, typed arrays, explicit GC หนึ่งกระบวนการ, หนึ่งวัตถุประสงค์, footprint น้อยที่สุด
3. **📈 Asymmetric upside** — คำสั่ง grid ขนาดเล็กที่อดทนเก็บ volatility หลายชัยชนะเล็ก ความเสียหายถูกจำกัดอย่างเข้มงวด หลายกลยุทธ์สำหรับหลาย regime
4. **🌐 การกระจายอำนาจคือความทนทาน** — ไม่มี single point of failure สองโหนดเทรด, coordinator กลาง, สถานะร่วม, failover อัตโนมัติ ฝูงรอดจากการ crash โหนด, exchange down, network partition

นี้ไม่ใช่บอท "ร่ำรวยเร็ว" นี่คือ **วินัยวิศวกรรมที่นำไปประยุกต์กับตลาด**: เริ่มด้วย €100, พิสูจน์กลยุทธ์บนกระดาษข้ามฝูงกระจาย, แล้ว — และเมื่อนั้นเท่านั้น — ขยาย.scale ด้วยความมั่นใจ

---

## 📜 Project History (ประวัติโครงการ)

| Milestone | Date / Commit | Description |
|-----------|---------------|-------------|
| **🌱 Live Bot (v0)** | pre-repo | บอท grid Kraken DOGE/EUR ไฟล์เดียว ทำงานจริงบน Raspberry Pi ~€200 หลายเดือน Systemd persistence, reload สถานะแมนว์ พิสูจน์แนวคิด; เปิดเผยขีดจำกัดของ monolith |
| **📉 The Binance Collapse** | 2026-06-29 → 07-01 | **โครงการเริ่มตกทะลวง — และยูโร** ฟล็อต live ของ Denaro ทำงานเต็มที่บน sub-account Binance… จนไม่ได้แล้ว Binance เพิกถอนสิทธิ์ trading API key sub-account EU แบบเงียบๆ บอทโหด, positions ค้าง, ~€206 แข็งกลาง grid สาเหตุ: **MiCA enforcement July 1, 2026** บทเรียน: **exchange risk คือ real risk** |
| **🐙 The Kraken Pivot** | 2026-07-01 | วันเดียวกัน: แปลงทั้งหมดเป็น EUR บน Binance (~€344 recovered), ถอน SEPA, โครงสร้างชี้ไป **Kraken** — MiCA-compliant, EU license, API ดีกว่า Binance/Bybit deprecated ถาวร |
| **🏗️ p1 — Modular Scaffold** | `504172c` | Refactor เต็มรูปแบบ Monolith แยก 5 โมดูล: `engine`, `exchange`, `strategy`, `state`, `risk` สถาปัตยกรรมจาก Freqtrade, Hummingbot, OctoBot, Jesse |
| **🔄 p2 — Paper Runner** | `0b2e0f3` | `PaperEngine` main loop: tick interval ปรับได้, grid wiring, persistence JSON Entry point `run_paper.py` |
| **🩹 p2.1 — Kraken Sandbox Fix** | `054b957` | CCXT Kraken ไม่มี `sandbox` Adapter จับ error fallback live readonly |
| **🛡️ p2.2 — Guard + Graceful Shutdown** | `015627a` | `getattr` guard vs `AttributeError`; SIGINT/SIGTERM handler หยุด engine, บันทึก portfolio, ออกสะอาด |
| **🧹 p3 — Infrastructure Cleanup** | — | ลบ **ทั้งหมด** legacy Denaro services, cron, systemd units, timers, binaries, orphaned processes ทั้งสองโหนด รอด: `denaro-paper` |
| **🧪 p4 — Paper Trading Test Suite** | current | 33 unit + integration tests Engine tick, risk gates, grid, trailing stop, paper exchange, backtest runner |
| **🌐 DDNS + Multi-Node Automation** | 2026-07-30 | **No-IP DDDS deployed ทั้งสองโหนด** (`nuvola` → `sgrivett.ddns.net`, `MARCODG1` → `mgrivett.ddns.net`) Systemd timer (10 min) + secure credential file |
| **🔑 API Key Rotation & Validation** | 2026-07-31 | **Kraken key หมุน** (post-MiCA) validated trading perms ✅ **MEXC keys validated ทั้งสองโหนด** Bybit deprecated (MiCA), removed |
| **💸 The 115 USDT Mystery** | 2026-07-22 | **115.74 USDT (ERC20) ส่ง Kraken — ไม่ถึง ไม่ on-chain** Kraken API ขาด funding perms Support ticket with TxID, proof |
| **🤖 Airdrop Farm v1** | 2026-07-31 | **Airdrop farmer อัตโนมัติ multi-strategy** บน nuvola (systemd) 20 wallets, 4 strategies, €250 virtual/€100 real Poisson scheduler, circuit breaker, idempotent Zabbix on MC2 |
| **🔄 Full Reboot & Verification** | 2026-07-31 | ทั้งสองโหนด reboot kernel updates Post-reboot: all systemd services healthy |
| **⚡ ShadowGrid v2.0 & Multi-Bot Fleet** | 2026-08-07 | **Transform เป็น 14-bot Adaptive Fleet ข้าม 2 exchange** ATR-adaptive spread, ADX/RSI momentum filter, 15% DD CB, 5% daily loss, 6% re-anchoring Fleet supervisor, pair scanner, rebalancer 14 bots, 200€ paper capital |
| **🛡️ ShadowGrid v2.1 — Risk & Alerts** | 2026-08-08 | **Portfolio risk management + multi-channel alerts** Risk Manager: correlation matrix, exposure limits, volatility targeting, risk parity, multi-layer kill switch Alert System: Telegram/Email/Log deduplication Dynamic pair selection: regime detection, performance decay, correlation filtering, weekly auto-rotation |
| **🏗️ ShadowGrid v2.2 — Unified Architecture** | 2026-08-09 | **Unification ShadowGrid v2 + neo** New `alpha_omega` package: UnifiedTradingEngine, DistributedFleetCoordinator, DistributedPairScanner, PortfolioRiskManager ZeroMQ Pub/Sub, Redis Streams, Raft leader election 24 bots (12/node), 200€ paper capital All audit issues resolved |
| **🚀 GO-LIVE — Live Trading with Real Capital** | **2026-08-10 22:42:30 CEST** | **€50 real capital deployed 2 nodes** OKX EEA endpoint (`eea.okx.com`) validated Kraken live keys validated 12 bots operational (6/node) Risk management armed Split-by-exchange architecture: Nuvola=Kraken, MARCODG1=OKX |
| **🏗️ v2.3 — สถาปัตยกรรม Split-by-Exchange** | **2026-08-11** | **แก้ไขคริติคอล: กำจัดการชนกันของบัญชี** Nuvola เทรด Kraken เท่านั้น (6 บอท) MARCODG1 เทรด OKX เท่านั้น (6 บอท) บัญชีร่วมต่อ exchange ไม่มีการชนกันของคำสั่ง Zabbix monitoring บน mc2 ทุนรวมที่ถูกต้อง: €50 (ไม่ใช่ €101) OKX WebSocket endpoint แก้ไขแล้ว (eea.okx.com) |
| **🔑 การตรวจสอบคีย์ API** | **2026-08-22** | **การทดสอบคีย์ API อย่างครอบคลุมบนทุกโหนด** คีย์ Kraken บน NUVOLA (2 คู่ทำงานได้, EUR=22.20), คีย์ OKX บน MARCODG1 (เสถียร 2+ วัน) แก้ไขปัญหา base64 padding และ IP whitelist ทุก exchange ทำงานได้ |
| **🤝 ความเข้ากันได้ระหว่าง Denaro-Atlas** | **2026-08-22** | **ชั้นความเข้ากันได้อย่างเป็นทางการระหว่าง Denaro (legacy เสถียร) และ Atlas (next-gen จัดการโดย Hermes)** ทั้งสองระบบอยู่ร่วมกันบนโหนดเดียวกันด้วยคีย์ API แยก Denaro รัน solo-engine (Kraken/OKX grid), Atlas ผ่าน Hermes AI ไม่มีความขัดแย้งด้วยการแยกคีย์ สถานะการทำงานเต็มรูปแบบบน NUVOLA และ MARCODG1 |

---

## 🏗️ Architecture (สถาปัตยกรรม)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ALPHA-OMEGA TRADING SYSTEM                              │
└─────────────────────────────────────────────────────────────────────────────┘

           ┌────────────────┐         ┌──────────────┐         ┌──────────────┐
           │     mc2      │◄───────►│    nuvola    │◄───────►│  MARCODG1    │
           │  (Home/DB)   │  ZeroMQ │  (Primary)   │  ZeroMQ │ (Secondary)  │
           └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
                  │                        │                        │
                  │         ┌──────────────┴──────────────┐        │
                  │         │        Redis Cluster        │        │
                  │         │   (Shared State + Streams)  │        │
                  │         └──────────────┬──────────────┘        │
                  │                        │                        │
                  ▼                        ▼                        ▼
         ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
         │ TimescaleDB   │         │  Kraken EUR   │         │  Kraken EUR   │
         │ Historical    │         │  OKX USDT     │         │  OKX USDT     │
         │ Zabbix/Alert  │         │  12 Bots      │         │  12 Bots      │
         └───────────────┘         └───────────────┘         └───────────────┘
 ```

## 🔬 Paper=Live Infrastructure Parity — Sandbox/Testnet Support

> **Paper trading environment ใช้ sandbox/testnet endpoints จริง ทำให้โครงสร้างพื้นฐานเหมือน live 100%**

### Supported Exchanges

| Exchange | Sandbox/Testnet | REST Endpoint | WS Endpoint | Auth |
|----------|-----------------|---------------|-------------|------|
| **Kraken** | Spot Pilot | `https://api.pilot.kraken.com` | `wss://ws.pilot.kraken.com` | HMAC-SHA512 |
| **OKX** | Demo Trading | `https://www.okx.com` (same) | `wss://ws.okx.com:8443/api/v5/market` | HMAC-SHA256 + `x-simulated-trading: 1` |
| **OKX EEA Live** | — | `https://eea.okx.com` | `wss://ws.okx.com:8443/api/v5/market` | HMAC-SHA256 + Passphrase |

---

## 🧪 Testing (การทดสอบ)

```bash
source venv/bin/activate
pip install pytest pytest-asyncio

# All tests
python -m pytest tests/ -v

# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Chaos engineering tests (requires running cluster)
python -m pytest tests/chaos/ -v
```

**Test Coverage Targets:**
- Unit: >90% (core buffers, state, risk, strategies)
- Integration: Market data → signal → order → fill → state sync
- Chaos: Node crash, network partition, exchange API down, Redis split-brain

---

## 📈 Deployment (การปรับใช้)

### Systemd Services (Bare Metal - Current Production)

**Fleet Coordinator** (`~/.config/systemd/user/shadowgrid-fleet.service`):

```ini
[Unit]
Description=ShadowGrid Fleet Orchestrator (Multi-Bot Grid)
After=network-online.target redis.service
Wants=network-online.target redis.service

[Service]
Type=simple
ExecStart=%h/denaro/venv/bin/python %h/denaro/shadowgrid_fleet.py
WorkingDirectory=%h/denaro
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

**Deploy Commands:**

```bash
# On each trading node (nuvola, MARCODG1)
git clone https://github.com/grivetto/alpha-omega-trading.git /home/sergio/denaro
cd /home/sergio/denaro
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure .env files for LIVE MODE
# LIVE_MODE=true, USE_SANDBOX=false, CAPITAL=25.0

# Install systemd services
sudo cp systemd/shadowgrid@.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start fleet (via fleet coordinator)
systemctl --user enable --now shadowgrid-fleet

# Health checks
curl http://localhost:8900/health | python3 -m json.tool
journalctl --user -u shadowgrid-fleet -f
```

### mc2 Coordinator Deployment

```bash
# On mc2
git clone https://github.com/grivetto/alpha-omega-trading.git
cd alpha-omega-trading
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.mc2.yml up -d

# Verify
curl http://localhost:3000  # Grafana
curl http://localhost:8080  # Zabbix
```

---

## 📊 Monitoring & Observability (การเฝ้าระวังและสังเกตการณ์)

### Key Metrics

| Category | Metrics |
|----------|---------|
| **Trading** | PnL (realized/unrealized), win rate, avg trade duration, Sharpe, Sortino, max DD |
| **Risk** | Portfolio DD, daily loss, exposure per base, correlation matrix, kill switch status |
| **System** | CPU, RAM, disk, FD count, network I/O, GC pauses, safe mode level |
| **Exchange** | API latency (p50/p95/p99), rate limit usage, order fill rate, slippage |
| **Fleet** | Bot count (running/error/draining), capital allocation, pair performance |

### Zabbix Integration
- **Templates**: `AlphaOmega Trading Node`, `AlphaOmega Fleet`, `AlphaOmega Coordinator`
- **Items**: All metrics above via HTTP `/metrics` endpoint (15 trapper items + daily cron)
- **Triggers**: DD > 10% (warning), DD > 15% (critical), bot down > 60s, safe mode >= SAFE, etc.
- **Actions**: Telegram/Email notifications, auto-restart via fleet coordinator

### Grafana Dashboards
1. **Fleet Overview**: Total equity, PnL, bot status, risk metrics, pair heatmap
2. **Node Deep Dive**: Per-bot performance, order book visualization, grid levels
3. **Risk Dashboard**: Correlation heatmap, exposure breakdown, DD waterfall, volatility regimes
4. **System Health**: Resource usage, latency percentiles, error rates, GC pauses

### Telegram Alerts
Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` for real-time:
- 🚨 CRITICAL: Portfolio DD > 15%, Daily loss > 5%, Kill switch, Bot repeatedly crashing
- ⚠️ WARNING: DD > 10%, Daily loss > 3.5%, Bot restart, Stuck bot, Volatility spike, Correlation breach
- ℹ️ INFO: Pair rotation, Volatility regime change, New pair added

---

## 🧘 Principles (หลักการ)

- **Modular architecture** — loosely coupled, easy to swap exchange, strategy, or risk model
- **Zero real risk** — circuit breakers at every layer: bot, portfolio, fleet
- **Deterministic backtesting** — same data, same results, every time
- **Transparent execution** — every order and fill logged to JSONL + Redis Streams
- **Production-ready** — systemd/Docker, graceful shutdown, state persistence, hot reload
- **Adaptive intelligence** — ATR-based spread, momentum filtering, regime detection, dynamic capital allocation
- **Distributed by design** — no single point of failure, automatic failover, shared state
- **Security first** — CURVE encryption, TLS everywhere, Vault secrets, 127.0.0.1 bind

---

## 🗺️ Roadmap (แผนทาง)

### ✅ Completed
- [x] p1 — Modular scaffold (engine, exchange, strategy, state, risk) — `neo/*`
- [x] p2 — Paper runner (live tick loop, grid strategy, portfolio persistence)
- [x] p3 — Infrastructure cleanup (deprecated services removed, single systemd unit)
- [x] p4 — Test suite (33 tests, engine integration, risk gates, backtest runner)
- [x] p4.5 — DDNS + multi-node automation (No-IP, systemd timers, secure creds)
- [x] p4.6 — API key rotation & validation (Kraken/MEXC, perms audit, Bybit deprecated)
- [x] p4.7 — Airdrop Farm v1 (20 wallets, 4 strategies, live on nuvola)
- [x] **⚡ ShadowGrid v2.0 & 14-Bot Fleet** — ATR-adaptive grid, ADX/RSI filter, fleet supervisor, pair scanner, rebalancer
- [x] **🛡️ ShadowGrid v2.1 — Risk & Alerts** — Portfolio risk manager, multi-channel alerts, dynamic pair selection
- [x] **🏗️ ShadowGrid v2.2 — Unified Architecture** — alpha_omega package, ZeroMQ/Redis, Raft, 24 bots
- [x] **🔍 Audit Fixes** — Legacy cleanup, health endpoint security, swap fix, config drift resolution
- [x] **🔬 Sandbox/Testnet Support** — Paper=Live infrastructure parity with Kraken Pilot + OKX Demo
- [x] **🚀 GO-LIVE — Live Trading** — €101 real capital, 24 bots operational, risk management armed

### 🎯 Next Phases

- [ ] **Phase 5 — Live Validation** (Week 1-4)
  - [ ] Live validation with €100 capital (1 month)
  - [ ] Scale to €1000 capital
  - [ ] Continuous optimization based on live metrics

- [x] **Phase 6 — Advanced Strategies** (Month 2) — **COMPLETED**
  - [x] Mean Reversion strategy (Bollinger + RSI) — `alpha_omega.strategies.mean_reversion`
  - [x] Momentum strategy (Donchian breakout + volume) — `alpha_omega.strategies.momentum`
  - [x] Scalp strategy (EMA crossover + volume) — `alpha_omega.strategies.scalp`
  - [x] DCA strategy (configurable entries, trailing) — `alpha_omega.strategies.dca`
  - [x] Grid strategy (ATR-adaptive + hybrid mode) — `alpha_omega.strategies.grid`
  - [x] Strategy Selector (regime-based switching) — `alpha_omega.strategies.selector`
  - [ ] Statistical Arbitrage (pair correlation + cointegration)
  - [ ] Funding Rate Arbitrage (perp vs spot)

- [x] **Phase 7 — Monitoring & Alerts** (Month 2) — **COMPLETED**
  - [x] Multi-channel Alert System (Telegram/Email/Zabbix/Log) — `alpha_omega.alerts.system`
  - [x] Alert Channels with deduplication — `alpha_omega.alerts.channels`
  - [x] Jinja2 Alert Templates — `alpha_omega.alerts.templates`
  - [x] Health Server with unified schema — `alpha_omega.monitoring.health`
  - [x] Prometheus/Zabbix Metrics Collector — `alpha_omega.monitoring.metrics`
  - [x] Resource Monitor with SafeMode — `alpha_omega.monitoring.resource`
  - [ ] ML-enhanced pair selection (XGBoost/LightGBM on regime features)
  - [ ] Regime detection with HMM/transformer
  - [ ] Dynamic spread optimization with RL
  - [ ] Anomaly detection for exchange issues

- [ ] **Phase 8 — Production Hardening** (Month 3-4)
  - [ ] HashiCorp Vault integration for secrets
  - [ ] WireGuard mesh for inter-node comms
  - [ ] Chaos engineering automation (Litmus/Gremlin)
  - [ ] Disaster recovery runbooks + drills
  - [ ] Multi-region deployment (EU + US)

- [ ] **Phase 9 — Scale** (Month 6)
  - [ ] 50+ bots across 3+ nodes
  - [ ] 5+ exchanges (Kraken, OKX, Binance.US, Coinbase, Bybit)
  - [ ] €10k+ capital under management
  - [ ] Institutional-grade reporting & compliance

---

## 📜 License (ใบอนุญาต)

[The Unlicense](http://unlicense.org/) — public domain. Do whatever you want.

---

## 🙏 Acknowledgments (ขอบคุณ)

- **CCXT** — Unified exchange interface
- **Freqtrade** — Architecture inspiration (strategy callbacks, dry-run, backtesting)
- **Hummingbot** — Clock/loop architecture
- **OctoBot** — Grid trading mode
- **Jesse** — Broker abstraction
- **ZeroMQ** — Ultra-low latency messaging
- **Redis** — Streams for persistent shared state
- **TimescaleDB** — Time-series data at scale
- **Zabbix + Grafana** — Observability stack
- **TA-Lib / Pandas** — Quantitative foundations

---

*Built with engineering discipline. Validated on paper. Ready for profit.* ⚡
