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
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-EUPL_1.1-blue.svg?style=flat-square" alt="EUPL 1.1 License"></a>
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> •
  <a href="README.it.md"><b>Italiano</b></a> •
  <a href="README.es.md"><b>Español</b></a> •
  <a href="README.th.md"><b>ไทย</b></a>
</p>

---

## 📊 Status at a glance — updated 2026-10-03

> **The fleet trades only what passes the gate — and the first live exception is on.** Since
> 2026-10-01 one real-money **canary** runs on OKX EEA: a DOGE funding carry (spot + perp hedge),
> fully reconciled, with funding accruing three times a day (day 3/14: funding +0.0076 USDC,
> net ≈ +0.009 USDC). Everything else still runs in paper while the research pays its toll. Size
> is deliberately small: it is an experiment, not a harvest.

| Area | State | Evidence |
| :--- | :--- | :--- |
| **Repository order** | ✅ reconciled with `origin`, all sessions' work committed | sessions' commits `[hermes]`/`[dsh]` pushed, `main` aligned (03/10) |
| **Test suite** | ✅ **finally executable** (was 63 failed / 50 errors, all environmental) — today **387 passed, 3 skipped** | see § Testing |
| **Order idempotency** | ✅ implemented (`clOrdId` on every dispatch, journaled *before* the order) | 7 tests |
| **Unfunded state** | ✅ explicit `ok` / `sottocapitalizzato` / `non_finanziato` / `illeggibile` | 18 tests |
| **Account exposure cap** | ✅ wired into the node (registry existed, nobody built it) | 15 tests |
| **Fleet integrity check** | ✅ `tools/fleet_integrity.py`, exit code 1 on any alarm | 14 alarms on MARCODG1, 7 on nuvola |
| **Live trading** | ✅ **one live bot** (carry C1, DOGE): size deliberately minimal, fully reconciled, funding accruing (funding +0.0076, net ≈ +0.009 USDC, day 3/14) | the project's first real execution; rest of the fleet: paper + research |
| **Capital** | ✅ **~1,100 EUR** on OKX (owner deposited **+1,000 EUR on 03/10**, verified read-only) | funding wallet; deployment gated on the 15/10 review |
| **Telemetry services** | ✅ clean sweep across the three nodes (03/10) + **post-reboot check 34/34** (`tools/postboot_check.sh`); the banco's declared un-funded exit (code 2) no longer surfaces as a systemd failure | `systemctl` sweep + `10-exit2.conf` drop-in |
| **Alerting** | ✅ Telegram channel live (`@DenaroAlertBot`): watchdog across **bots · canary · fleet** (anti-flap on 2 consecutive detections, recovery message) + 09:00 digest | zero-silence initiative |
| **Squad & agents** | ✅ **8 executors + 1 director** on 3 machines: `A0-win` · `A0-mc2` · `DSH-mc2/omarchy/win` · `opencode-mc2/omarchy` · `agy-omarchy` — every delivery reviewed by Hermes, tests re-run in-repo | see § The operations layer |
| **Security** | ⚠️ one host was compromised, now contained | see § Security |
| **Economy** | ⚠️ current fee tier cancels the edge — see § The economics | measured on real fees |

---

## 📜 The story — from «La Baracca» to a measured fleet

The project was originally nicknamed *«La Baracca»* — Italian for a makeshift contraption always
needing another patch. The name aged well: for a year it was exactly that — bots that ran, numbers
that did not reconcile, zero euros earned, through several attempts and several AI tools (OpenClaw,
Hermes, Agent Zero, DeepSeek TUI). The turning point was not a feature. It was a decision: stop
building, start measuring — and make the measuring a gate.

| When | What happened | The lesson it left |
| :--- | :--- | :--- |
| **2026, spring → summer** | The `denaro` series: four codebases one after another — Binance on a phone, a first `money` (grid, DCA, scalper, hedge, futures, sentiment), **this** repository (49,162 lines, 17 bots, three machines), `denaro2` on the VPSes | building the system *first* and looking for something to capture *afterwards* does not work |
| **2026-09** | The audit (`docs/01`): «the system works, on an unsupervised baracca» — unversioned services, capital the accounts did not have, 1,486 ticks lost silently, 10 of 12 outages from one stale path | stop; re-found |
| **2026-09-23 → 30** | The re-foundation: three nodes = three families = three accounts; risk becomes a portfolio property (2% / −3% / −10%); the **8-criteria gate** becomes code; experiments are pre-registered and judged one by one | the gate is not a guideline: it is code, and its rejection is binding |
| **2026-10-01** | **The first real order of the project** executes on OKX EEA; the **canary C1** (DOGE funding carry) opens — minimal size, fully reconciled | an experiment, not a harvest |
| **2026-10-03** | Owner deposits **+1,000 EUR**; the fleet gains its agents (`DSH`, `A0`, `opencode`, `agy`), live alerting, and a post-reboot check (34/34) | capital does not create the edge — it makes the gain *visible* |

The old codebases live in the sibling [`money`](https://github.com/grivetto/money) repository —
`legacy/`, tracked with their history, memory rather than foundation. Research happens there;
**nothing reaches production without passing the gate.**

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

<p align="center">
  <img src="assets/architettura-flotta.svg" alt="Fleet architecture: three nodes, one OKX sub-account each, one portfolio risk governor" width="100%"/>
</p>

### The operations layer — the same machines, second role (rev. 2026-10-03)

One machine = one strategy family = one sub-account is the *trading* design. The same three
machines also carry everything that builds, watches and guards the fleet: a hub, an operations
room and a monitoring post.

```
               ┌──────────────────── OKX EEA (eea.okx.com) ─────────────────────┐
               │ live: 1 canary carry (DOGE) · the rest: paper — no orders      │
               └────────────────────────▲──────────────────────▲────────────────┘
                           orders       │                      │  market data / public API
 ┌─────────────────────────────────────┴──┐  ┌───────────────┴───────────────────┐
 │ mc2 — hub & workshop                   │  │ MARCODG1 — operations room        │
 │ · Hermes — direction, code, review     │  │ · aggregator :8912 → 34 bots      │
 │ · fabric master — one action every 3 s │  │ · dashboard :8913 · landing :8914 │
 │ · Zabbix 7.0 (Docker) + alerting       │  │ · Grafana :3000 · health :8911    │
 │ · A0-mc2 coder · DSH-mc2 (dsh-web)     │  │ · canary (live) · dry bench       │
 │ · fabric worker — every 5 s            │  │ · fabric worker — every 5 s       │
 └────────────────────────────────────────┘  └───────────────────────────────────┘
 ┌────────────────────────────────────────┐
 │ nuvola — monitoring post               │
 │ · health :8911 · exporter :9100        │
 │ · Zabbix agent + tunnel → mc2          │
 │ · fabric worker — every 5 s            │
 └────────────────────────────────────────┘
 ┌────────────────────────────────────────┐
 │ agents node (Omarchy, LAN) — agents    │
 │ · DSH-omarchy — harness + dsh-web      │
 │ · opencode-omarchy · agy-omarchy       │
 └────────────────────────────────────────┘
   telemetry: paper fleet (simulated, all three nodes) → aggregator → dashboard + landing →
   Zabbix «Money» (38 hosts — bots, machines, project; auto-heal on known faults)
```

**The live bot** — since 01/10 a real bot trades on OKX EEA: carry **C1** (DOGE spot + X-Perp
short, 1× isolated, size deliberately minimal), fully reconciled against the exchange; funding
accrues three times a day (00/08/16 UTC) and the net is slightly positive (day 3/14: funding
+0.0076 USDC, net ≈ +0.009 USDC). The 14-day validation window closes on **15/10** with
pre-registered criteria (`docs/16`). It is the project's **first real execution**: everything else
stays paper + research.

On **03/10** the owner deposited **+1,000 EUR** (OKX funding wallet, verified read-only:
+1,000.00 exact) to fund the carry scale-up — deployment gated on the **15/10** review.

![Denaro system — 03/10/2026](assets/foto-sistema-2026-10-03.png)

*Full-resolution visual: [`FOTO_SISTEMA_2026-10-03.html`](https://github.com/grivetto/money/blob/main/FOTO_SISTEMA_2026-10-03.html) · squad: [`FOTO_SQUADRA_2026-10-03.html`](https://github.com/grivetto/money/blob/main/FOTO_SQUADRA_2026-10-03.html) (sibling `money` repo).*

**In pratica** — work flows through one loop with a small bench of executors: two Agent Zero coders
(`A0-mc2` and `A0-win` on the PC), three DSH instances (`DSH-mc2`, `DSH-omarchy` research peer,
`DSH-win` legacy peer), free OpenCode executors (`opencode-mc2`, `opencode-omarchy`) and
`agy-omarchy` (Antigravity) — plus the **agents node** (Omarchy, LAN), wired to the same channel and
review loop. Every delivery is reviewed by Hermes with the tests re-run in the repository before
anything lands; research itself lives in the sibling repo
[`money`](https://github.com/grivetto/money): idea → pre-registered spec → executor → review →
measure → 8-criteria gate → promote or archive → dry bench → canary → minimum-size live.
Heartbeats and freshness checks cover every critical daemon: the fabric tick and the node shards
are watched, and Zabbix auto-heals known fault patterns while raising the rest.

![The squad — 03/10/2026](assets/foto-squadra-2026-10-03.png)

### Core technologies

| Component | Tech | Function |
| :--- | :--- | :--- |
| **Language / runtime** | Python 3.12+, AsyncIO | node event loop, policies, supervisor |
| **Exchange access** | CCXT 4.x — OKX EEA REST **and** WebSocket (`ccxt.pro`), hostname **`eea.okx.com`** | market data and order routing; EU keys work *only* against the EEA endpoint |
| **Execution core** | Python, AsyncIO, CCXT | policies (trend / adaptive grid / mean-reversion), order lifecycle, fill accounting |
| **Risk core** | Pure domain modules, no I/O | Per-trade risk, circuit breaker, account exposure cap, funding classification |
| **Backtest** | Own engine, fee- and slippage-aware | The same decision code as live: one rig for both |
| **Fleet ops** | systemd (system + user units, `linger`), SSH, Tailscale, Cloudflare Tunnel | No inbound exposure; telemetry only on loopback |
| **Telemetry** | Zabbix 7.0 LTS (one agent per host), Prometheus, Grafana, health endpoints | Equity curves, tick health, staleness badges |
| **Integrity** | `tools/fleet_integrity.py` + `tools/postboot_check.sh` | Miner / crontab / sudoers / unit-path / port checks, with exit code; one-command post-reboot verification (34 checks) |
| **Packaging** | Docker + `docker-compose`, `venv`, `requirements.txt` | Reproducible environments across three hosts |
| **Quality** | pytest (**387 passed, 3 skipped**), ruff | A suite that can be executed is the precondition for verifying anything |
| **CI** | GitHub Actions | lint and tests on push |
| **Config & secrets** | YAML node configs, one `.env_<node>` per node (mode 600, gitignored) | One account per node, isolated by `env_prefix` |
| **Version control** | git, one writer per path | Provenance: who changed what, and when |

---

## 🧪 Testing — and why it was the biggest fix of this cycle

```bash
python -m pytest denaro/tests -q      # 387 passed, 3 skipped
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

**Done since (2026-10-01):** Zabbix credentials rotated; monitoring frontend behind Cloudflare Access; plaintext secrets purged from this repository. **Still open for the owner:** revoke the GitHub PAT found in clear text in a shell history; decide whether to rebuild the compromised host; regenerate the key vault (7 of 7 OKX
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

# post-reboot verification (34 checks across all nodes)
bash tools/postboot_check.sh

# tests
python -m pytest denaro/tests -q

# a node
python -m denaro.denaro_node --config config/node_nuvola_trade.yaml

# honest backtest against real fees
python -m denaro.backtest --config config/node_nuvola_trade.yaml --days 60 --fee 0.0035
```

---

## 🚧 Open work, in order of value

1. **Canary C1 review — 15/10.** The 14-day validation window closes with pre-registered criteria
   (`docs/16`); the multi-pair carry scale-up deploys right after a green light — plan written and
   ready (`money/docs/20`), owner-gated.
2. **The first promoted edge is still missing — the honest headline.** Every strategy family
   measured so far is archived; the live thesis (funding carry) is in validation, not yet promoted.
   Research continues in the sibling repo (P-series registry, M1 validation release).
3. **DSH-win backlog**: several requests await an owner turn on the Windows peer (file channel
   `hermes_bridge/dsh/`).
4. **Minor known gaps, kept honest:** grid fill recording fallback (carried since 09/25); async
   tests still run through an undocumented mechanism.
5. **Keep the workshop a workshop:** everything that restarts has a check
   (`tools/postboot_check.sh`, verified 34/34 post-reboot), and everything that breaks has an alert
   (`@DenaroAlertBot`, watchdog across bots · canary · fleet).

## 🗺 Scaling path

The structure is identical at every scale: **one node = one strategy = one account**. What changes
is the *number of nodes*, not the number of strategies packed onto one account. Packing them
together is the experiment already run — and it produced 14% aggregate risk, bots halting each
other on shared equity, and one stop liquidating another bot's inventory.

- [x] **Now:** repository in order, three critical defects closed with proof, integrity check
      operational, suite executable, infrastructure versioned (`deploy/`).
- [x] **Then:** the fee gate — derivatives opened on OKX EEA (`acctLv 2`); the tooling is back in
      a position to use it.
- [x] **2026-10-03:** owner deposited **+1,000 EUR**; capital is staged, deployment gated on the
      **15/10** canary review.
- [ ] **Next:** the first promoted edge out-of-sample — everything else already waits for it.

---

## ⚖️ Disclaimer

**This software is distributed strictly for educational, academic, and research purposes. It is not
financial or investment advice.** Cryptocurrency algorithmic trading involves substantial financial
risk, including the possible loss of all invested capital. The authors make no representations or
warranties regarding system profitability or performance. Never trade with capital you cannot
afford to lose.

---

## 📄 License

Released under the **European Union Public Licence v. 1.1 (EUPL-1.1)**. See [LICENSE](LICENSE).
