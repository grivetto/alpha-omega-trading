# Alpha-Omega Trading — «Denaro»

<p align="center">
  <img src="assets/banner.svg" alt="Alpha-Omega Trading Banner" width="100%"/>
</p>

<h3 align="center">A measured algorithmic trading fleet: three machines, complementary strategies, isolated sub-accounts</h3>

<p align="center">
  <i>Independent multi-node execution engine on OKX EEA, with hard risk budgets, honest telemetry, and a promotion gate that no strategy enters production without passing.</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://www.okx.com/en-eu"><img src="https://img.shields.io/badge/OKX-EEA-000000?style=flat-square" alt="OKX EEA"></a>
  <a href="https://github.com/ccxt/ccxt"><img src="https://img.shields.io/badge/CCXT-4.x-1E88E5?style=flat-square" alt="CCXT"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://www.zabbix.com/"><img src="https://img.shields.io/badge/Zabbix-7.0_LTS-D40000?style=flat-square&logo=zabbix&logoColor=white" alt="Zabbix 7.0 LTS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-CC0_1.0-blue.svg?style=flat-square" alt="CC0 License"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> •
  <a href="README.it.md"><b>Italiano</b></a> •
  <a href="README.es.md"><b>Español</b></a> •
  <a href="README.th.md"><b>ไทย</b></a>
</p>

---

## 📊 Status at a glance — 2026-09-25

> **The fleet is NOT trading right now, and it is not supposed to be.** Every live node currently
> reports `NON FINANZIATO`: the exchange accounts behind the live API keys hold **~0.15 EUR of
> dust**. The engine refuses to trade a balance it cannot honestly measure, and as of this release
> it *says so* instead of skipping ticks in silence. Funding is a deliberate, separate decision.

| Area | State | Evidence |
| :--- | :--- | :--- |
| **Repository order** | ✅ reconciled with `origin`, all sessions' work committed | 5 commits published, `main` aligned |
| **Test suite** | ✅ **finally executable** (was 63 failed / 50 errors, all environmental) | see § Testing |
| **Order idempotency** | ✅ implemented (`clOrdId` on every dispatch, journaled *before* the order) | 7 tests |
| **Unfunded state** | ✅ explicit `ok` / `sottocapitalizzato` / `non_finanziato` / `illeggibile` | 18 tests |
| **Account exposure cap** | ✅ wired into the node (registry existed, nobody built it) | 15 tests |
| **Fleet integrity check** | ✅ `tools/fleet_integrity.py`, exit code 1 on any alarm | 14 alarms on MARCODG1, 7 on nuvola |
| **Live trading** | ⛔ account balance is dust (~0.15 EUR) | journal: 882 + 604 skipped ticks |
| **Telemetry services** | ⚠️ 4 units in pathological restart (path drift) | `denaro-watchdog` failed |
| **Security** | ⚠️ one host was compromised, now contained | see § Security |
| **Economy** | ⚠️ current fee tier cancels the edge — see § The economics | measured on real fees |

---

## 🏛 Fleet topology

The system runs across three hosts, each an **independent node: one machine = one strategy family =
one OKX sub-account**. This is not a stylistic choice — it is the correction of three defects that
were observed in production (see § Lessons).

```
 ┌──────────────────────────────────────────────────────────────┐
 │                    EXCHANGE LAYER — OKX EEA                  │
 │         (EU keys only work against eea.okx.com)              │
 └───────┬──────────────────┬──────────────────┬────────────────┘
         │                  │                  │
 ┌───────▼────────┐ ┌───────▼────────┐ ┌───────▼──────────────┐
 │ NODE A         │ │ NODE B         │ │ NODE C               │
 │ nuvola         │ │ mc2            │ │ MARCODG1             │
 │ TREND (daily)  │ │ GRID adaptive  │ │ 4H momentum          │
 │ sub: nuvolasub1│ │ sub: mc2sub1   │ │ sub: marcosub1       │
 │ edge MEASURED  │ │ gate: to be    │ │ gate: needs fees     │
 │                │ │ measured       │ │ below 0.30%/side     │
 └────────────────┘ └────────────────┘ └──────────────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │ PORTFOLIO RISK GOVERNOR    │
              │ one budget: 2% of capital  │
              │ daily stop −3%, max DD −10%│
              └────────────────────────────┘
```

**Three rules that are not negotiable:**

1. **One account per strategy.** No bot shares a sub-account with a different strategy.
2. **Risk is a portfolio property, not a per-bot property.** The 2% budget is of *total* capital.
   Seven bots each declaring the whole account risked **14% of the account, not 2%** — measured by
   `tools/audit_capitale_config.py`.
3. **No strategy enters production without passing the gate**: positive net expectancy
   out-of-sample, at the *real* costs of the account it runs on.

### Core technologies

| Component | Tech | Function |
| :--- | :--- | :--- |
| **Execution core** | Python, AsyncIO, CCXT | Policies (trend / adaptive grid / mean-reversion), order lifecycle, fill accounting |
| **Risk core** | Pure domain modules, no I/O | Per-trade risk, circuit breaker, account exposure cap, funding classification |
| **Backtest** | Own engine, fee- and slippage-aware | The same decision code as live: one rig for both |
| **Fleet ops** | systemd, SSH, Tailscale, Cloudflare Tunnel | No inbound exposure; telemetry only on loopback |
| **Telemetry** | Zabbix, Prometheus, Grafana, dashboards | Equity curves, tick health, staleness badges |
| **Integrity** | `tools/fleet_integrity.py` | Miner / crontab / sudoers / unit-path / port checks, with exit code |

---

## 🧪 Testing — and why it was the biggest fix of this cycle

```bash
python -m pytest denaro/tests -q      # 382 passed, 3 skipped
```

For weeks the suite reported **63 failed and 50 errors**. Almost none of them were code defects:
they were **permission errors of the environment**. The root cause, isolated with three direct
probes:

```
os.makedirs(<repo>/.pytmp/probe) + write   -> OK
tempfile.mkdtemp()               + write   -> PermissionError
os.makedirs(...) + open(...)     -> OK
```

`tempfile.mkdtemp` is refused while `os.makedirs` works — and both `TemporaryDirectory` and
pytest's `tmp_path` go through it. The consequence was the real damage: **two independent work
sessions could not verify anything**, and a suite whose result is noise cannot protect anything.
`denaro/tests/conftest.py` now replaces it at the root: the outcome went from *63 failed / 50
errors* to **1 real failure**, which is a known semantic gap (see § Open work).

---

## 💰 The economics — said plainly

The decisive number is not the strategy, it is the toll. Measured from official OKX EEA fee pages:

| account | maker | taker | round trip | break-even gross edge per trade |
| :--- | :--- | :--- | :--- | :--- |
| OKX EEA **without** derivatives (today) | 0.200% | **0.350%** | **0.700%** | **0.70%** |
| OKX EEA **with** X-Perps opened | 0.080% | **0.100%** | **0.200%** | 0.20% |

Opening a derivatives account on OKX EEA does **not** require volume or capital — only KYC plus an
*appropriateness assessment*. It moves the account from the 0.35% table to the 0.10% table.

**And a correction that had been circulating for days:** the daily trend's `−1.97%` is a
**cumulative alpha over 2.4 years**, not a daily return. At zero cost the signal is significant
(t = +4.51); at 0.35% per side it is **indistinguishable from zero** (t = −0.30). It is not a
strategy that bleeds — it is a strategy the toll erases.

The two levers that actually multiply:

- **lower the toll** — 0.70% → 0.20% per round trip, which multiplies sustainable frequency by 3.5×;
- **raise the frequency** — the 4H family goes from 3/24 to 18/24 robust configurations at the same
  lower fee, i.e. ~8× the opportunities.

Neither of the two is code. One is an assessment; the other is its consequence.

---

## 🛡 Risk management

- **Per-trade risk** — 2% of capital, fixed in configuration and published in health.
- **Circuit breaker** — daily stop at −3%, maximum drawdown at −10%, persisted across restarts.
- **Account exposure cap** — the *sum* of all bots on the same sub-account, not per bot.
- **Funding classification** — a node with no capital declares `NON FINANZIATO` once per
  transition, places no orders, and never pollutes peak / daily / weekly baselines. It exits the
  state on its own when funds arrive, without a restart.
- **Order idempotency** — every dispatch carries a `clOrdId`, journaled *before* the order leaves;
  an order that survives a crash is recognised as ours on restart instead of counted as unknown.
- **Stop semantics** — the stop sells the bot's own claim (`tracked size + bought-not-resold`),
  never the account's free balance: with two bots on one sub-account, the old behaviour liquidated
  another bot's inventory.
- **Supervisor** — RAM/CPU pressure throttles tick intervals (`nominal` → `caution` → `safe` →
  `emergency`).

---

## 🔒 Security — one host was compromised, now contained (2026-09-25)

An audit of the fleet found a **third-party cryptominer** on MARCODG1: an ELF binary in
`/var/tmp/.X11-unix-socket/`, running as the `zabbix` service user for **4 days**, 199% CPU and
2.1 GB RAM, with cron persistence and a live connection to a mining pool. It was the direct cause of
the live node's `SafeMode safe ↔ caution` flapping (RAM at 87%).

Containment, with forensic copies taken **before** any deletion:

| action | verified outcome |
| :--- | :--- |
| process terminated | no PID, 0 pool connections |
| RAM | used **3114 → 1003 MB** |
| cron persistence | removed (spool verified on disk) |
| binary | `chmod 000` + copy in `/root/quarantena_miner_20260925/` |
| orphan `sudo` rule for `zabbix` | removed → *not allowed to run sudo* |
| `AllowKey=system.run[*]` | disabled on **both** hosts |

**Open for the owner:** revoke the GitHub PAT found in clear text in a shell history; rotate Zabbix
credentials; decide whether to rebuild the compromised host; regenerate the key vault (7 of 7 OKX
keys in it are dead); review the firewall (`ufw` inactive, `5432` and `10050` exposed).

---

## 📚 Lessons ("La Baracca")

The project was originally nicknamed *"La Baracca"* — Italian for a makeshift contraption always
needing another patch. The name aged well. What the live markets taught, in order of cost:

1. **Fragmented capital deadlocks.** Small balances spread over many sub-accounts, each with open
   orders, reduce free balance to zero.
2. **The toll is not a detail.** Fees and slippage silently cancel edges that backtests show
   comfortably.
3. **Every bot declaring the whole account multiplies risk by N.** Seven bots × 2% = 14%.
4. **A guard without a state is a silent failure.** 1,486 skipped ticks looked like "nothing
   happened" for hours, because no state said "I am not funded".
5. **Untracked orders after a crash are invisible money.** Hence idempotency keys.
6. **Telemetry that reads like a fossil is worse than no telemetry.** Stale health files count as
   "running" unless something explicitly checks their age.
7. **Production path drift breaks everything at once.** Ten of twelve broken units shared one root
   cause: a stale project path in systemd units and crontabs that were never versioned.

---

## 🛠 Quick start

```bash
git clone git@github.com:grivetto/alpha-omega-trading.git
cd alpha-omega-trading
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env         # credentials stay local: never commit secrets

# integrity check of the machine (read-only, exit code 1 on alarm)
python tools/fleet_integrity.py
python tools/fleet_integrity.py --host nuvola --host MARCODG1 --host mc2

# tests
python -m pytest denaro/tests -q

# a node
python -m denaro.denaro_node --config config/node_nuvola_trade.yaml

# honest backtest against real fees
python -m denaro.backtest --config config/node_nuvola_trade.yaml --days 60 --fee 0.0035
```

---

## 🚧 Open work, in order of value

1. **Record the grid position on fill.** The one remaining real test failure: a grid buys, the fill
   is not recorded as an open position, and the stop falls back to deducing it from sell orders.
   Correct, but not sufficient.
2. **Test isolation.** One test passes alone and fails in the suite → shared state between tests.
   Related: `pytest-asyncio` is not installed and `asyncio_mode` is an unknown option, so async
   tests currently run through an unexplained mechanism.
3. **Telemetry** — 4 units in pathological restart, all from `~/denaro` vs `~/alpha-omega-trading`
   path drift.
4. **Version the infrastructure** (`deploy/systemd/`, `deploy/cron/` with a parameterised
   `PROJECT_ROOT`): the root cause of 10 of 12 broken units, and of the blindness about who changed
   what.
5. **Capital.** The decisive variable, and deliberately separate from the code.

## 🗺 Scaling path

The structure is identical at every scale: **one node = one strategy = one account**. What changes
is the *number of nodes*, not the number of strategies packed onto one account. Packing them
together is the experiment already run — and it produced 14% aggregate risk, bots halting each
other on shared equity, and one stop liquidating another bot's inventory.

- [x] **Now:** repository in order, three critical defects closed with proof, integrity check
      operational, suite executable.
- [ ] **Next:** grid fill recording, test isolation, telemetry repaired, infrastructure versioned.
- [ ] **Then:** the fee gate — put **one** account into a clean state and request the derivatives
      upgrade. It touches no deployment, it is reversible, and it is the only action that unlocks
      frequency.
- [ ] **Then:** staged capital, and only on out-of-sample evidence.

---

## ⚖️ Disclaimer

**This software is distributed strictly for educational, academic, and research purposes. It is not
financial or investment advice.** Cryptocurrency algorithmic trading involves substantial financial
risk, including the possible loss of all invested capital. The authors make no representations or
warranties regarding system profitability or performance. Never trade with capital you cannot
afford to lose.

---

## 📄 License

Dedicated to the public domain under Creative Commons Zero (CC0 1.0 Universal). See [LICENSE](LICENSE).
