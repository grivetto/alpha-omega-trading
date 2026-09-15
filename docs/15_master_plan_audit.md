# Alpha-Omega Trading — Master Plan: Audit, Enhancement, Architectural Optimization

**Date:** 2026-09 (branch `consolidation/fleet-order-2026-09`)
**Scope:** the whole `denaro` package (76 modules), `config/*`, `denaro/tests` (23 suites),
the fleet docs in `docs/`, and the strategy registry that feeds runtime promotion.
**Method:** every claim below is grounded in a read of the source, a reproduction run, or a test.
Nothing is reported from intuition. The reproduction harness and the regression suite ship with
this document.

---

## 0. How this audit was performed (and how to re-verify it)

| Step | Command / artifact | Result |
| :--- | :--- | :--- |
| Static recon | `denaro/` module line census, import graph | 76 modules, ~11k LOC in `denaro/` |
| Ground-truth tests | `pytest denaro/tests` | **baseline: 35 failed, 161 passed, 30 errors** (most failures were the DSH file-sandbox denying `tempfile` writes — see §0.1) |
| Runtime reproduction | `.pytmp/repro_audit.py` (5 defects) | all 5 confirmed empirically |
| Fix + regression | `denaro/tests/test_hardening.py` (23 new tests) | **final: 223 passed, 0 failed** |
| Lint | `ruff check denaro` | **All checks passed** (was 4 errors, 2 of them real defects) |

### 0.1 A note on the test environment

`tempfile.mkdtemp` creates directories with mode `0o700`; the DSH file sandbox then denies writes
inside them, which makes a large part of the suite fail with `PermissionError` for reasons that have
nothing to do with the code. To get a real signal I ran the suite with a local (non-committed)
`sitecustomize` shim under `.pytmp/` that creates temp dirs with inherited ACLs. That shim is
**not** part of the deliverable.

After the fixes, the only non-passing tests are 4 in `test_overrides.py`, which depend on pytest's
`tmp_path` fixture and are blocked by the same sandbox issue. Their logic was verified
independently (all 5 override behaviours, including the whitelist and corrupt-file tolerance) — see
§7. **No application-level test failure remains.**

---

## 1. Critical Vulnerabilities & Bottlenecks Found

Severity: **P0** = money-losing or fail-safe-breaking; **P1** = correctness/perf; **P2** = hygiene.

### P0-1 · Unbounded duplication of the bilateral sell ladder *(FIXED)*

`denaro/domain/grid.py` + `denaro/application/orchestrator.py`

```
REPRODUCED — open_sells per tick on a flat market, zero fills:
[2, 4, 6, 8, 10, 12]      # +2 orders every tick, forever
```

Two independent defects compounded:

1. **Wrong dict key.** `GridPolicy.decide` de-duplicated with `float(s.get("price") or 0)`, but the
   orchestrator stored sells under `target_price` only (orchestrator.py:343, :646). `s.get("price")`
   was therefore **always `None`** → the guard could never fire.
2. **Moving anchor.** Even with the right key, `sell_price = price * (1 + dist)` was re-derived from
   the *current* tick price every cycle, so exact-equality de-duplication can never hold in a moving
   market.

**Why it matters:** with `sell_levels: 2` on both live OKX bots (`config/node_mc2.yaml`) and
`tick_interval: 30`, that is ~240 duplicate orders per hour per bot. Free asset gets locked in
duplicate orders (the sell ladder *is* the mechanism that funds the buy side), the exchange starts
rejecting, and `_process_fills` — which iterated `open_sells` with **one REST call per order** —
degrades linearly. Self-reinforcing latency spiral.

**Fix:** the ladder is now *level-indexed and anchor-stable*:
* ladder sells are tagged `kind="ladder"` + `level=L`; TP sells are tagged `kind="tp"`;
* occupancy is computed from the tag, with a **price-proximity fallback** for orders reloaded from
  the exchange after a restart;
* the anchor is *recovered* from existing tagged orders rather than re-read from the last price;
* a stale ladder (market outside the retarget band) is explicitly cancelled and re-anchored;
* the per-level share is computed on `free_asset + our_locked_ladder`, so the ladder cannot shrink
  itself;
* **hard invariant: never more than `sell_levels` ladder sells open**, enforced by a budget counter.

### P0-2 · Risk state was never persisted — the circuit breaker could be disarmed by a restart *(FIXED)*

`denaro/application/orchestrator.py`

```
REPRODUCED — same bot, same state_path, new process:
before restart: peak=44.0  trade_results=6  consecutive_losses=3
after  restart: peak=30.0  trade_results=0  consecutive_losses=0
```

`BotTask.__init__` built a fresh `CoreState(...)`, and `_save_state()` persisted **only**
`BotState`. `CoreState` — peak/daily/weekly baseline, `cb`, `perf`, `trade_results`, Kelly,
VaR — was reconstructed from defaults on every boot.

**Why it matters:** the daily and weekly hard stops (`daily_loss_limit`, `weekly_loss_limit`) and
the drawdown breaker are the last line of defence on a small account. A crash-loop, a systemd
restart, or an operator restart silently reset them. Sharpe/Sortino/Calmar/ProfitFactor telemetry
(pushed to Zabbix/dashboard) also restarted from zero every time, so the numbers the fleet reports
have **never** been a running record.

**Fix:** a full serialization codec for the nested dataclass tree in `denaro/domain/types.py`
(`CoreState.to_dict()` / `from_dict(data, base)`), a second `StateStore` per bot
(`..._risk.json`), and a merge-on-load that keeps the bot's own capital as the baseline instead of
the dataclass default `100.0`. An unparseable CB state now resolves to **`OPEN`** (fail-safe), not
`CLOSED`. `trade_results` is bounded to the last 500 entries on write.

### P0-3 · `KrakenPermanentError` referenced but never imported *(FIXED)*

`orchestrator.py:403` used `except Exception as e: if isinstance(e, KrakenPermanentError):` while
the name existed only inside `kraken.py`. Any permanent cancel failure (e.g. `EOrder:Unknown order`)
raised `NameError` **inside the except block**, aborting the whole tick.

**Fix:** a shared taxonomy in `denaro/infrastructure/exchanges/errors.py`
(`ExchangeError` → `PermanentExchangeError` / `TransientExchangeError`), with the historical
adapter classes re-parented onto it. The orchestrator now catches `PermanentExchangeError`, covering
both adapters and any future one.

### P0-4 · The EMERGENCY fail-safe never completed *(FIXED)*

`denaro/denaro_node.py` uses `time.time()` in `_on_emergency` but **never imports `time`**.

```python
async def _on_emergency(self):
    for ...: cancel_all(...); self.sqlite.save(symbol, ...)
    self.sqlite.save("guardian", {"ts": time.time(), ...})   # NameError here
    self._stop.set()                                          # NEVER REACHED
```

The NameError is swallowed by `SafeModeGuardian.run`'s blanket `except Exception`. Net effect:
at >95 % RAM the guardian cancels orders and then **the controlled shutdown never fires** — the node
keeps running and OOMs. This is precisely the failure the mechanism exists to prevent. Found by
`ruff` (`F821`), not by any test.

**Fix:** imported `time` and `Optional`; added a regression test that asserts
`_on_emergency()` actually sets the shutdown event.

### P0-5 · `Policy.on_fill` was never called — every stateful policy was blind *(FIXED)*

```
REPRODUCED — policy.on_fill invocations after a completed buy fill: 0
```

`BotTask._process_fills` updated `BotState` and the journal, but never notified the policy. The
`on_fill` contract exists in the domain layer and is implemented by `VagrPolicy`, `IrmrPolicy`,
`MinCaptureGrid`, `AdaptiveVolGrid`, `CyclePhaseGrid` — and was dead for all of them. Consequences:
`_inventory_quote` stayed `0.0` forever, so inventory caps, mean-reversion gating and
`mr_inventory_band_pct` throttling never engaged.

**Fix:** `BotTask._notify_fill`, a **name-aware** dispatcher. Arity alone cannot disambiguate
`(order_id, side, price, size)` from `(side, price, qty, fee, ts)` when `fee`/`ts` have defaults, so
it maps parameter *names* onto the canonical roles and falls back to positional binding, then to a
single-dict signature. Errors inside a policy's `on_fill` are logged, never propagated (the Journal
remains the authority).

### P0-6 · `_guard_equity` blocked the event loop, and its coherence check was dead code *(FIXED)*

Two defects in one 25-line method:

* it called `self.ex.fetch_balance()` **synchronously on the event loop** — including the
  adapter's `time.sleep()` rate-limit and exponential-backoff retries. A single suspicious equity
  reading could freeze **every bot on the node** for seconds.
* the "Fix B1" coherence path tested `inspect.iscoroutinefunction(price)` where `price` was already
  the *result of calling* the price source (a coroutine **object**). `iscoroutinefunction` is always
  `False` for an object, so the check never engaged and `float(coroutine)` raised `TypeError`,
  silently swallowed. For live bots — the only case it was written for — the code was unreachable.

**Fix:** `async def _guard_equity`, all I/O via `asyncio.to_thread`, correct
`asyncio.iscoroutine` handling on the price source, and the same bug fixed in
`_trigger_stop_loss` (where `float(coroutine)` meant the stop-loss sell price was **always logged as
0.0**).

### P0-7 · Two bots on one sub-account share one equity (the risk controls cross-contaminate) — *NOT FIXED, blueprinted*

`NodeApp._equity_for` returns `exchange.fetch_total_equity`, which values the **entire account**.
`config/node_mc2.yaml` runs `DOGE/EUR` **and** `SOL/EUR` on the same OKX sub-account
(`mc2sub1`). Both bots therefore:

* compute the *same* peak, drawdown and `max_dd`;
* share one `stop_loss_pct` trigger — a DOGE drawdown stops SOL and vice-versa, simultaneously;
* push the same equity to two different health files, so the dashboard double-counts.

`fetch_total_equity` also issues **one `fetch_ticker` per non-quote asset** in the account, on
every tick, via `to_thread` — an unbounded per-tick REST fan-out that grows with account dust.

This is deliberately **not** patched. A wrong change to live stop-loss semantics is worse than the
known-shared behaviour. The design is in §3.1 (per-bot capital ledger) and it is a prerequisite for
Stage 2 capital scaling, not a nice-to-have.
### P0-8 · VAGR's kill-switch was dead and its volatility estimator was double-fed *(FIXED)*

`denaro/domain/vagr.py`

* `_daily_loss` was initialised to `0.0` and **never assigned anywhere else**. Both
  `kill_switch_drawdown_pct` and `max_daily_loss_pct` compared against it, so the VAGR kill-switch
  could never fire.
* `decide()` called `self.on_price(price)`, while `BotTask.tick()` had **already** called
  `policy.on_price(price)`. Every tick was ingested twice, so the Welford mean/variance of the true
  range was computed over a doubly-sampled series.
* Compounding it: `on_price` fabricates `high = price*1.0005`, `low = price*0.9995`, so the "true
  range" is a **constant `0.001·price`** regardless of the market. `spacing = (atr/price)·vol_target·10
  = 0.0008` then always clamps to `min_spacing_pct = 0.002`. **In live operation VAGR is a fixed
  0.2 % grid, not a volatility-adaptive one.** The docstring and the README both claim otherwise.

**Fix (part 1):** an ingestion latch (`_fed_since_decide`) guarantees exactly one ingest per tick
whether `decide` is called alone or after `on_price`; `on_fill` now maintains average cost and
accumulates realized daily loss; a UTC day roll re-arms the kill-switch. **Fix (part 2) — real
high/low into the ATR — is blueprinted in §3.3** because it requires plumbing OHLCV into the policy
contract.

### P0-9 · The entire ResourceSupervisor was non-functional *(FIXED)*

* `ResourceSupervisor._default_metrics()` returned `NodeMetrics()` — **all zeros** — and
  `NodeApp` never injected `get_metrics`. `check()` therefore always computed `ram_used = 0.0` and
  returned `"nominal"`.
* `adjusted_interval()` was referenced **only in tests**. `BotTask.run()` slept on
  `self.cfg.tick_interval` directly.
* `_read_metrics()` (which parses `/proc/self/status`) was defined and never called.

Net: the "adaptive throttling / zero-OOM backpressure" advertised in the README did not exist.
Every bot kept full tick frequency precisely when the node was under pressure.

**Fix:** the default metrics provider now reads real RSS/CPU via `psutil`;
`TradeOrchestrator.start_all` injects the supervisor into each bot; `BotTask._tick_interval()`
applies `adjusted_interval`.

### P0-10 · The "centralized" rate limiter was per-adapter *(FIXED)*

`RateLimiterRegistry` and `AsyncTokenBucket` were used **only in tests**. `build_exchange` created a
fresh adapter per bot, and `OKXAdapter.__init__` did `bucket or TokenBucket(10, 5)` — so N bots on
one exchange meant N independent budgets of 10 tokens @ 5/s. The documented "one budget per
exchange, shared by all bots" was false. The hub used a *third*, separate ccxt-internal limiter.

**Fix:** `NodeApp` owns a `RateLimiterRegistry` and passes one bucket per **exchange name** into
`build_exchange`; `rate_limits` is now a declared field in the Pydantic `NodeConfig` (see P1-6).

### P0-11 · Strategy promotion has no out-of-sample gate *(NOT FIXED — governance blueprint in §3.6)*

`config/strategies/registry.json` (57 kB) holds a `best_candidate` per symbol which an external
optimizer writes. The live node then merges it into the bot at start-up
(`NodeApp._apply_overrides`). Observed for `SOL/EUR`:

```json
"best_candidate": {
  "params": {"strategy":"grid","buy_distance":0.005,"profit_target":0.01,"levels":2,
             "sell_levels":3,"stop_loss":0.1,"adx_threshold":25},
  "metrics": {"ret":0.0303,"max_dd":0.0943,"sharpe":-8.137,"win_rate":1.0,
              "trades":137,"n_bars":223}
}
```

* **223 bars ≈ 9 days of 1h data.** Every parameter above was selected on that single in-sample window.
* `sharpe = -8.137` **together with** `win_rate = 1.0`: the selection objective is the closed-cycle
  win rate — exactly the metric `denaro/backtest/metrics.py` opens its docstring by warning against
  ("the metric that made drawdown invisible in production").
* `trade_pnls` values (0.79, 0.84, 0.88, 1.29 …) imply ~6–7 % per closed cycle, implausible for a
  1 % `profit_target` grid — strongly suggests a capital-base or unit mismatch in the optimizer.
  **This deserves a dedicated investigation before any further promotion.**
* **No walk-forward, purged CV, PBO or deflated-Sharpe code exists anywhere in the repo** (grep for
  `walk_forward|oos|deflated|purged|optuna|hyperopt` returns only prose in `docs/07_audit_5_pilastri.md`
  and unrelated `streak_boost` matches). The walk-forward approach is *proposed in a doc* and never
  implemented.
* `_OVERRIDE_KEYS` (denaro_node.py:42) whitelists `capital`, `stop_loss_pct`,
  `max_drawdown_limit`, `daily_loss_limit`, `weekly_loss_limit`. An automated optimizer can
  therefore **widen the risk envelope** it is being judged against, with no ceiling and no audit trail.

### P1-1 · Event-loop-blocking durability I/O *(FIXED)*

`Journal.append` does `flush() + os.fsync()` per record; `AtomicFile`/StateStore and
`_write_health` do synchronous `write + os.replace`. All of it ran on the event loop. On a 30 s tick
with 2 bots this is 3 file writes + up to 2 fsyncs per bot per tick, serialized across all bots.

**Fix:** `_journal` is now `async` (`asyncio.to_thread`), and `_persist()` batches
state + risk-state + health into **one** `to_thread` call — replacing the 3 scattered synchronous
write sites on every early-return path in `tick()`.

### P1-2 · N+1 REST fan-out in fill reconciliation *(FIXED)*

`_process_fills` issued one `fetch_order` per tracked order, **sequentially**, twice per tick. With
the P0-1 bug inflating `open_sells`, tick duration grew monotonically. **Fix:** one
`fetch_open_orders` (already fetched for the portfolio — now threaded through) to identify open ids,
and a `fetch_order` **only** for orders that disappeared from the open set, i.e. only on the tick
where something actually changed. Steady-state REST calls drop from `2·(buys+sells)` to 1.

### P1-3 · Regime filter is built on an unconverged EMA200 *(NOT FIXED — §3.3)*

`denaro/domain/regime.py` seeds the EMA with the first sample and `TradeOrchestrator.OHLCV_LIMIT = 200`
while `EMA200_PERIOD = 200`. With `alpha = 2/201 ≈ 0.00995`, the weight still sitting on the *first*
candle after 200 steps is `(1-alpha)^200 ≈ 0.135`. The time constant is ~100 bars. So the BULL/BEAR
classification — and the `ema_series[-11]` slope, a 10-bar slope of a 100-bar-time-constant filter —
are dominated by the seeding artefact. Also noted: `_wilder_smooth()` is a dead stub returning
`values[-1]`; `_atr_pct` uses a simple mean while `_adx` uses Wilder smoothing; `_rsi` is Cutler's
RSI, not Wilder's — three inconsistencies with the module docstring.

### P1-4 · The WebSocket channel permanently degrades to REST and never recovers

`MarketDataHub._ws_loop`: after `ws_max_retries` failures it `await`s `_rest_loop(symbol)` and
returns. There is no path back to WebSocket for the process lifetime. With `ws_enabled: true` in
`node_mc2.yaml`, a single network blip permanently downgrades the node to REST polling
(`poll_interval: 10`) — with higher latency (stale prices feed the grid) and higher rate-limit
pressure. `price_ttl: 30` also means `get_price` can serve a 30 s-old price as if fresh.

### P1-5 · Unbounded journal growth

`Journal.read_all()` reads the whole JSONL into memory, and it is called by
`_rebuild_from_exchange` at every boot (and by `__len__`). Trade history is append-only and
unrotated; startup cost and RSS grow without bound. `trade_results` is now capped, but the file is not.

### P1-6 · Pydantic silently discards unknown config keys (a recurring bug class)

`NodeConfig` is a `BaseModel` with default `extra='ignore'`. The codebase already documents two
production incidents caused by this (`config.py:80-82` — the bilateral sell ladder never placed
because `sell_levels` was missing from the schema; `config.py:125-127` — an instance pointed at the
wrong overrides file). Any new operational key is dropped without a warning. I hit it again while
adding `rate_limits`, which would have been silently ignored.

### P2 — hygiene and lower-severity items

| # | Finding | Location |
| :--- | :--- | :--- |
| P2-1 | `_guard_equity`'s plausible range `[5 %, 30×]` **masks real drawdowns**; the backtest itself counts `equity_guard_hits` and labels them "livello mascherato" | orchestrator.py, metrics.py:113 |
| P2-2 | `BotState.from_dict` silently ignores renamed/removed keys → undetected state schema drift | orchestrator.py:74 |
| P2-3 | SafeMode monitors RAM % only — no swap, no file-descriptor or disk pressure; `on_change` propagation is a fire-and-forget loop over bots | safemode.py |
| P2-4 | `AtomicFile` temp name is `<path>.tmp`, not unique per writer — safe today (single writer) but a landmine if two processes ever share a state path | storage.py:31 |
| P2-5 | No client order id (idempotency key) on placement. Crash-between-place-and-save *is* recovered by exchange reconciliation, but a retry can still duplicate | okx.py / kraken.py |
| P2-6 | `SqliteStateStore` is only used in the EMERGENCY path; `journal_mode=WAL` is asserted in tests but the store is never used for normal operation, so the "SQLite/Postgres failover" claim has no implementation | sqlite_store.py |
| P2-7 | `scripts/hermes_moa_anti_refusal.py`, `scripts/patch_moa_aggregator.py` and 4 `docs/` files are untracked working-tree artifacts unrelated to trading | repo root |

---

## 2. Strategy & Market Analysis Review

### 2.1 What the live fleet actually runs

| Bot | Symbol | Strategy | Params | Effective behaviour today |
| :--- | :--- | :--- | :--- | :--- |
| mc2 #1 | DOGE/EUR | `grid` | levels 3, buy_dist 1.5 %, TP 2 %, `sell_levels` 2, SL 10 % | static grid + bilateral ladder (P0-1 broke the ladder) |
| mc2 #2 | SOL/EUR | `grid` | same | same, **shared equity with #1** (P0-7) |
| MARCODG1 | SOL/EUR, XRP/EUR | `momentum` | TP 2 %, slip 0.2 % | EMA/ADX momentum capture |

Available but not deployed: `meanrev`, `adaptive`, `irmr`, `vagr`, `mincapture`,
`cycle_phase`, `flowgate`, `asymvol_anchor`. `adaptive_vol_grid` is reachable only as a
standalone/CSV strategy.

### 2.2 Indicator and alpha-quality assessment

* **Grid (live):** statically spaced levels, TP = fixed fraction of entry. No volatility scaling, no
  edge gate, no inventory-aware sizing. On a 1.5 % spacing with `fee: 0.001` per side, round-trip fee
  is 0.2 % and the TP is 2 % — thin but viable; the *ladder* side is where the economics actually leak,
  because ladder sells at +2 %/+3 % are placed regardless of the fee/slippage-adjusted edge.
* **Momentum (live):** `denaro/domain/momentum.py` tracks an EMA history fed from **tick prices** via
  `on_price`, not from OHLCV. It inherits the same estimator-quality problem as VAGR: tick sampling
  is irregular and price-only, so an "EMA" over tick samples is a time-weighted artefact, not a
  market-time indicator.
* **VAGR:** nominally volatility-adaptive; **demonstrably constant-spacing** in live operation (P0-8).
* **IRMR / MinCapture / CyclePhase:** implement `on_fill` state that was never fed (P0-5) — all
  inventory gates were inert.
* **Microstructure:** `MicroState` and `RegimeState` already declare
  `bid_ask_spread_pct`, `bid_ask_imbalance`, `cum_bid_depth_1pct`, `order_book_slope`,
  `spoofing_flag`, `support_levels`, `resistance_levels` — and **nothing in the codebase ever
  populates them**. The highest-value unbuilt capability in this repo is sitting as unused fields.

### 2.3 Risk, slippage and drawdown enforcement — verified behaviour

| Control | Where | Verdict |
| :--- | :--- | :--- |
| Per-bot stop-loss (close positions, not just block) | `BotTask._trigger_stop_loss` | **Correct logic, and it is the one control that survived.** Cancels both sides, market-sells free base, persistent flag, spread guard, fails open when unmeasurable. Now also persists across restart. |
| Circuit breaker (daily/weekly/drawdown, vol-scaled limits) | `RiskManager.check_circuit_breaker` | Correct, **but was reset on every restart** (P0-2). Recovery transitions and the `sizing_multiplier` ladder are sound. |
| Kelly sizing / vol targeting | `RiskManager.kelly_fraction`, `risk_sized_capital` | Mathematically reasonable and unit-consistent (verified `normal + kelly 0.25 → ×1.0`). **The Kelly fraction is never fed by `calculate_kelly()`** — the "Kelly" in use is the static base 0.25 × multipliers, not an estimated edge. |
| Slippage model | `stop_loss` spread guard (live), `PaperExchange(slippage=)` / `SimExchange` (paper/backtest) | Stop-loss guard is real. **Grid TP fills assume zero slippage**; only the paper/backtest layer models it. |
| Max drawdown limit | `RiskManager.max_drawdown_limit` (config 15 %) + per-bot `stop_loss_pct` (10 %) | Both enforced; but **masked by `_guard_equity`** when equity reads outside `[5 %, 30×]` (P2-1). |
| Exposure cap | `RiskManager.exposure_limit`, `risk_sized_capital` | Implemented, **not wired** into `GridPolicy.decide` — the latter receives `risk_capital` and divides by `levels`, which is a proxy, not the exposure cap. |
| Fee accounting | `_process_fills` (`proceeds·(1-f) - cost·(1+f)`) | Correct and matches the backtest. Live configs use `fee: 0.001`; `AdaptiveVolGrid`/VAGR default to `0.0026` (Kraken taker). **Make sure the live bot's configured `fee` matches its actual maker/taker schedule — the whole edge lives here.** |

### 2.4 Overfitting exposure — the honest assessment

The backtest harness itself is **good work**: head-line metric is mark-to-market equity return (not
realized cycle PnL), benchmarked against buy-and-hold on the same capital, fee-accounted, and the
runner deliberately mirrors the live control flow ("parità LIVE"). The docstring in
`backtest/metrics.py` shows the author understood exactly why realized-cycle PnL lies.

But a parity harness is **not** a validation protocol, and it has three specific weaknesses:

1. **No out-of-sample discipline.** One pass over one window. No train/test split, no walk-forward,
   no embargo. 223 bars was enough to promote a `sharpe = -8.1` candidate (§P0-11).
2. **Parity propagates bugs as if they were features.** `runner.py:334-342` reproduces the
   ladder-duplication bug *verbatim* (`open_sells[o["id"]] = {... "target_price": ...}`, no `kind`,
   no `level`), and lines 311-326 reproduce the VAGR double-`on_price` feed. So the backtest agreed
   with a broken live system — and would have "validated" it. *Parity with a biased estimator is not
   validation.* Both are now fixed at the source, which fixes the backtest too.
3. **The optimizer's objective is the metric the project itself declared unreliable**
   (`win_rate`/`trade_pnls`), and the promoted candidate's `trade_pnls` magnitudes don't reconcile
   with its own `profit_target`.
---

## 3. Refactored Strategy Blueprints

All blueprints obey the existing contracts (`GridDecision`, `Policy.decide/sell_target/on_price/on_fill`,
the `ExchangePort` protocol) so they drop into the current pipeline without breaking
backward compatibility. Config keys are additive; every one must be **declared in the Pydantic
schema** or it will be silently dropped (P1-6).

### 3.1 Per-bot capital ledger — prerequisite for everything else

Fixes P0-7 and unblocks Stage 2. New file `denaro/application/ledger.py`:

```python
@dataclass(frozen=True)
class Allocation:
    """Quota di capitale assegnata a UN bot su un account condiviso."""
    bot_key: str
    quote_budget: float          # EUR riservati a questo bot
    base_budget: float = 0.0     # asset iniziale assegnato (seeded)

class CapitalLedger:
    """Alloca quote di un account tra N bot e ne calcola l'equity per-bot.

    La somma delle quote NON puo' superare il saldo reale: l'ultimo bot a
    reclamare riceve il residuo, cosi' l'account resta sempre completamente
    allocato e nessun bot puo' vantare capitale che un altro sta usando.
    """

    def __init__(self, allocations: Sequence[Allocation]) -> None:
        self._alloc = {a.bot_key: a for a in allocations}

    def equity(self, bot_key: str, free_quote: float, base_qty: float,
               price: float) -> float:
        a = self._alloc[bot_key]
        # il bot vede SOLO la propria quota, non l'intero sub-account
        quote_share = min(free_quote, a.quote_budget)
        base_share = min(base_qty, a.base_budget) if a.base_budget else base_qty
        return quote_share + base_share * price
```

Wiring in `NodeApp._equity_for` → return a closure bound to `(bot_key, ledger, exchange)` instead of
the raw `exchange.fetch_total_equity`. Config:

```yaml
accounts:
  okx:mc2sub1:
    bots: [okx:mc2sub1:DOGE/EUR, okx:mc2sub1:SOL/EUR]
    allocations:
      okx:mc2sub1:DOGE/EUR: {quote_budget: 6.0}
      okx:mc2sub1:SOL/EUR:  {quote_budget: 6.0}
```

Also add `fetch_equity_for(symbol)` to both adapters (`free(quote) + (free+locked)(base)·price`) so the
per-bot equity reads exactly the assets that bot can trade.

### 3.2 Order-book imbalance microstructure gate *(highest expected value)*

Turns the unused `MicroState` fields into a real signal. Two new modules.

**(a) `denaro/infrastructure/orderbook.py`** — a hub-side subscriber mirroring `MarketDataHub`:

```python
@dataclass
class BookSnapshot:
    bid: float; ask: float; ts: float
    spread_pct: float
    imbalance_1pct: float          # (bid_depth - ask_depth) / total
    slope: float                   # depth decay coefficient (log-fit)
    spoof_score: float             # 0..1, see _spoof_score

class OrderBookHub:
    """Un canale watch_order_book per symbol, condiviso da tutti i bot.

    Pubblica una MicroState normalizzata; NON decide nulla (domain purity).
    """

    def __init__(self, ex_pro, depth: int = 20, ttl_s: float = 5.0) -> None: ...

    async def _loop(self, symbol: str) -> None:
        book = await self._ex.watch_order_book(symbol, limit=self._depth)
        snap = self._reduce(book)               # pura, testabile offline
        self._cache[symbol] = (snap, self._now())

    @staticmethod
    def _reduce(book) -> BookSnapshot:
        bid, ask = book["bids"][0][0], book["asks"][0][0]
        mid = (bid + ask) / 2
        bid_d = sum(p * q for p, q in book["bids"] if p >= mid * 0.99)
        ask_d = sum(p * q for p, q in book["asks"] if p <= mid * 1.01)
        total = bid_d + ask_d or 1.0
        return BookSnapshot(bid=bid, ask=ask, ts=book["timestamp"] / 1000.0,
                            spread_pct=(ask - bid) / mid,
                            imbalance_1pct=(bid_d - ask_d) / total,
                            slope=_depth_slope(book),
                            spoof_score=_spoof_score(book))
```

**(b) domain gate** `denaro/domain/micro_gate.py` — pure, no I/O:

```python
@dataclass(frozen=True)
class MicroGateParams:
    max_spread_pct: float = 0.004        # sopra: non piazzare (fee/slippage)
    adverse_imbalance: float = -0.35     # bid depth molto piu' sottile dell'ask
    spoof_threshold: float = 0.7
    size_factor_at_max_imbalance: float = 0.5

class MicroGate:
    """Veto/sizing dal book. NON supera mai 1.0 (non aumenta l'esposizione)."""

    def __init__(self, p: MicroGateParams = MicroGateParams()) -> None:
        self.p = p

    def evaluate(self, micro: BookSnapshot, side: str) -> tuple:
        if micro.spread_pct > self.p.max_spread_pct:
            return False, 0.0, f"spread {micro.spread_pct:.3%}"
        if micro.spoof_score >= self.p.spoof_threshold:
            return False, 0.0, "order book sospetto (spoofing)"
        if side == "buy" and micro.imbalance_1pct <= self.p.adverse_imbalance:
            return False, 0.0, f"imbalance avverso {micro.imbalance_1pct:+.2f}"
        # sizing continuo: book favorevole -> 1.0, avverso -> floor
        factor = 1.0 if micro.imbalance_1pct >= 0 else max(
            self.p.size_factor_at_max_imbalance,
            1.0 + micro.imbalance_1pct * (1.0 - self.p.size_factor_at_max_imbalance))
        return True, factor, "ok"
```

**Integration point** — `BotTask.tick`, after the price fetch and before `policy.decide`:

```python
micro = self._micro_source(self.cfg.symbol) if self._micro_source else None
if micro is not None and self._micro_gate is not None:
    ok, factor, why = self._micro_gate.evaluate(micro, "buy")
    if not ok:
        decision.to_place = []
        decision.reason = f"micro gate: {why}"
    else:
        risk_capital *= factor
```

**Why this first:** at 12 EUR per bot the binding constraint is *cost and adverse selection*, not
signal scarcity. Vetoing buys into a widening spread and thinning bid book is the cheapest available
edge, it is symmetric to the existing stop-loss spread guard, and it fails safe (no book → no veto).

### 3.3 Multi-timeframe regime + honest volatility estimation

Fixes P1-3 and completes P0-8. New `denaro/domain/mtf_regime.py`:

```python
@dataclass(frozen=True)
class MtfParams:
    timeframes: tuple = ("1d", "4h", "1h")
    ema_period: int = 200
    min_bars_for_ema: int = 600      # >= 3x period: EMA convergente
    donchian_period: int = 55        # breakout alternativo, non un EMA ri-seedato
    require_daily_agreement: bool = True

class MtfRegimeFilter:
    """Regime multi-timeframe con VETO gerarchico.

    Regola: il timeframe lento decide la DIREZIONE ammessa, il veloce decide il
    TIMING. Una griglia che compra mentre il 1d e' ribassista e' un coltello che
    cade: e' esattamente il pattern che ha prodotto gli inventory trap descritti
    nel README ("Unchecked buy-ladders during sudden sell-offs").
    """

    def classify(self, bars_by_tf: Mapping) -> "MtfRegime":
        per_tf = {}
        for tf, bars in bars_by_tf.items():
            if len(bars) < 30:
                per_tf[tf] = None
                continue
            closes = [b[4] for b in bars]
            ema = (_ema_converged(closes, self.p.ema_period)
                   if len(closes) >= self.p.min_bars_for_ema else None)
            per_tf[tf] = _TfView(
                adx=_adx(bars), atr_pct=_atr_pct(bars),
                ema=ema, donchian=_donchian(bars, self.p.donchian_period),
                hurst=hurst_exponent(closes), last=closes[-1])
        return self._combine(per_tf)
```

`_ema_converged` must either (a) require `len >= 3·period`, or (b) warm-start by seeding with
`SMA(period)` over the first `period` bars and discarding those bars from the output. Either way,
**raise `OHLCV_LIMIT` to ≥ 600** and stop treating a 200-sample EMA200 slope as a trend signal.
Replace or augment the EMA with Donchian (55) + Hurst, which are far less seed-sensitive.

**Plumbing real OHLCV into the volatility estimators** (completes P0-8 — VAGR and
`AdaptiveVolGrid` are still fed synthetic ±5 bp ranges in live operation):

1. Add `on_ohlcv(ohlcv)` to the policy contract (optional, like `on_price`).
2. `TradeOrchestrator.add_ohlcv_source` already exists and already calls
   `getattr(policy, "on_ohlcv", None)` — but **only `AdaptiveEngine` implements it**. Implement it
   on `VagrPolicy` (feed true ranges into the Welford accumulator) and on `AdaptiveVolGrid`.
3. Until then, **disable VAGR in production** — its advertised adaptivity does not exist, and its
   `min_spacing_pct` floor is doing all the work.

### 3.4 Adaptive statistical arbitrage (pairs)

New `denaro/domain/statarb.py`, plus the execution caveat below.

```python
@dataclass(frozen=True)
class StatArbParams:
    lookback: int = 720              # barre 1h per la stima di cointegrazione
    refit_every: int = 24
    entry_z: float = 2.0
    exit_z: float = 0.0
    stop_z: float = 3.5              # la relazione e' rotta: esci, non mediare
    min_half_life_bars: float = 4.0
    max_half_life_bars: float = 120.0
    fee_rate: float = 0.001
    min_edge_mult: float = 3.0       # |entry_z| * sigma_spread > mult * fee_round_trip

class PairsStatArb:
    """Mean reversion su spread cointegrato, con test di stazionarieta' CONTINUO.

    Il punto che distingue una stat-arb da una scommessa: la relazione viene
    RI-TESTATA a ogni refit. Se Engle-Granger non rifiuta la non-stazionarieta'
    del residuo, o se l'half-life esce dalla banda, la coppia viene DISATTIVATA
    finche' non torna valida. Nessun averaging-down su una relazione rotta.
    """

    def fit(self, y, x):
        beta, alpha = _ols(y, x)
        resid = [yi - (alpha + beta * xi) for yi, xi in zip(y, x)]
        if not _adf_stationary(resid):
            return None
        hl = _half_life(resid)              # AR(1) su delta_resid
        if not (self.p.min_half_life_bars <= hl <= self.p.max_half_life_bars):
            return None
        return SpreadModel(alpha=alpha, beta=beta,
                           mu=_mean(resid), sigma=_std(resid), half_life=hl)
```

**Execution caveat (must be solved before this is safe).** `BotTask` is single-symbol: a pair position
is two legs that must be sent together or hedged immediately. Sending leg A and failing leg B converts
a market-neutral trade into a directional one. Add a `PairBotTask` that owns two `ExchangePort`s and
an explicit two-phase commit:

```python
async def _open_pair(self, y_leg, x_leg) -> bool:
    """Leg rischiosa prima, hedge subito dopo; su fallimento, CHIUDI la prima."""
    leg_y = await self._place(y_leg)
    if not leg_y:
        return False
    try:
        leg_x = await self._place(x_leg)
    except Exception:
        leg_x = None
    if not leg_x:
        await self._unwrap(leg_y)         # riporta a flat: niente esposizione nuda
        await self._journal("pair_leg_failed", y=leg_y)
        return False
    return True
```

Do **not** deploy pairs until §3.1 (per-bot ledger) and the two-phase commit are in place, and only
with capital ≥ Stage 2. At 12 EUR the round-trip fee on two legs eats the spread many times over
before the strategy can work.

### 3.5 RL-based execution: scope it honestly

**Recommendation: do not use RL for alpha generation on this system, and do not use policy-gradient
methods at this capital level.** With ~50 EUR deployed, 2 bots and a handful of closed cycles per day,
the sample complexity of a function-approximation RL agent is orders of magnitude away from being
estimable. An RL agent fitted here will learn the simulator, not the market.

What *is* defensible, and useful, is **execution scheduling** on a small discrete action space — a
contextual bandit, not a deep policy:

```python
@dataclass(frozen=True)
class ExecutionActions:
    """Spazio d'azione DISCRETO e interpretabile (3x3 = 9 azioni)."""
    order_type: str          # "post_only" | "marketable_limit" | "market"
    spacing_mult: float      # 0.75 | 1.0 | 1.5

@dataclass
class ExecutionBandit:
    """LinUCB/Thompson su contesto a bassa dimensionalita'.

    Contesto: (spread_pct, imbalance_1pct, realizzato_vol, inventory_pct,
    minuti_dall_ultimo_fill, regime_one_hot).
    Reward: PnL realizzato NETTO di fee e slippage, meno una penalita' per
    adverse selection misurata a +N tick dall'ingresso.

    Garanzie richieste prima di andare live:
      * exploration floor (epsilon >= 0.1) - mai sfruttamento puro;
      * shadow mode per >= 2 settimane con confronto contro la baseline fissa;
      * kill-switch: se il regret rolling supera la soglia, si torna alla baseline;
      * il bandit NON puo' cambiare size ne' rischio, solo il tipo/spacing.
    """
```

The reward function must include adverse selection, otherwise the bandit will happily learn to place
marketable limits that fill instantly into a falling book — the classic way RL execution silently
destroys a mean-reversion edge.

### 3.6 Walk-forward promotion gate (fixes P0-11)

New `denaro/backtest/walkforward.py` + `denaro/application/promotion.py`. This is a **governance**
fix and it is more valuable than any new indicator.

```python
@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 1500
    test_bars: int = 500
    embargo_bars: int = 24           # purga: nessun overlap fra train e test
    min_folds: int = 4
    min_trades_oos: int = 30
    max_pbo: float = 0.25            # Probability of Backtest Overfitting
    min_deflated_sharpe: float = 0.0
    max_dd_oos: float = 0.12
    risk_ceiling_keys: tuple = (
        "stop_loss_pct", "max_drawdown_limit", "daily_loss_limit",
        "weekly_loss_limit", "capital")

def evaluate_candidate(cfg, bars, params) -> "PromotionVerdict":
    """Verdetto OOS su fold purgati. Ritorna PROMOTE / REJECT con motivazione.

    Regole non negoziabili:
      1. la metrica di selezione e' il rendimento MTM OOS vs buy&hold, non il
         win rate dei cicli chiusi (vedi backtest/metrics.py);
      2. almeno min_trades_oos operazioni OOS, altrimenti REJECT (campione
         insufficiente e' un rifiuto, non un'incertezza);
      3. PBO <= max_pbo e deflated Sharpe > 0;
      4. il candidato NON puo' ALLARGARE l'inviluppo di rischio rispetto
         all'incumbent: i risk_ceiling_keys sono monotoni (solo piu' stretti).
    """
```

And the parameter governance: `promotion.py` should be the **only** writer of
`config/strategy_overrides.json`, and `_OVERRIDE_KEYS` should be split into
`_OVERRIDE_KEYS_TUNABLE` (geometry only) and `_OVERRIDE_KEYS_RISK` (accepted only if strictly
tightening the incumbent), with an append-only audit record of every promotion
(candidate, folds, OOS metrics, verdict, hash of the data window).

### 3.7 Fee-aware edge gate for every policy

Generalises `AdaptiveVolGrid._fee_ok` — the single most important economic guard for micro capital.
New `denaro/domain/edge.py`, applied in `BotTask.tick` after `decide()`:

```python
@dataclass(frozen=True)
class EdgeGateParams:
    fee_rate: float
    min_edge_mult: float = 2.5       # il TP deve coprire >= 2.5x il costo round-trip
    expected_slippage: float = 0.0005
    min_edge_abs: float = 0.0        # opzionale: floor assoluto sull'edge

class EdgeGate:
    """Filtra i TP che non coprono i costi. NON blocca le USCITE."""

    def target_is_viable(self, entry: float, target: float) -> bool:
        gross = (target - entry) / entry
        cost = 2.0 * self.p.fee_rate + 2.0 * self.p.expected_slippage
        return gross >= self.p.min_edge_mult * cost and gross >= self.p.min_edge_abs
```

Wiring: in `_process_fills`, before placing the TP sell, consult the gate; if the policy's target is
not viable, widen it to the minimum viable target (or hold) and journal the decision. **Never** apply
the gate to stop-loss or ladder exits.
---

## 4. Production-Ready Code Snippets — Critical Path

### 4.1 Already applied in this change set

```
denaro/infrastructure/exchanges/errors.py     NEW  shared error taxonomy (P0-3)
denaro/domain/types.py                        +124 persistent CoreState codec, fail-safe CB (P0-2)
denaro/domain/grid.py                         +125 level-indexed, budget-capped sell ladder (P0-1)
denaro/application/orchestrator.py            +450 async equity guard, async journal, batched
                                                   persist, open-orders reconciliation,
                                                   name-aware on_fill dispatch, quote currency,
                                                   PermanentExchangeError handling
denaro/application/supervisor.py               +26  real psutil metrics (P0-9)
denaro/application/config.py                   +10  declared rate_limits schema (P1-6)
denaro/denaro_node.py                          +43  time/Optional imports (P0-4), risk_state_path,
                                                   shared TokenBucket per exchange (P0-10),
                                                   equity caveat documented (P0-7)
denaro/domain/vagr.py                         +101  ingestion latch, realized-PnL kill-switch,
                                                   UTC daily re-arm (P0-8)
denaro/tests/test_hardening.py                 NEW  23 regression tests
```

The two optimizations with the largest measured effect on the critical path:

**Latency — fill reconciliation (`_process_fills`).** Before: `fetch_order` per tracked order,
sequential, twice per tick. After:

```python
open_ids = None if open_orders is None else {str(o.get("id")) for o in open_orders}

async def _resolved_status(oid: str) -> str:
    """'open' se ancora aperto; altrimenti interroga l'ordine singolo."""
    if open_ids is not None and oid in open_ids:
        return "open"
    try:
        o = await asyncio.to_thread(self.ex.fetch_order, oid, self.cfg.symbol)
    except Exception:                       # non risolvibile: non toccare lo stato
        return "open"
    return str(o.get("status", "open"))
```

Steady state drops from `2·(buys+sells)` REST calls to **1** (`fetch_open_orders`, already needed for
the portfolio), with the per-order call paid only on transitions.

**Event loop — durability (`_persist`).** One `to_thread` for state + risk-state + health, replacing
three synchronous write sites on every early-return path:

```python
async def _persist(self, equity: float, blocked: bool, free_quote: float = 0.0) -> None:
    def _write() -> None:
        self._save_state()          # state.json + risk.json (tmp+rename, atomico)
        self._write_health(equity, blocked=blocked, free_quote=free_quote)
    await asyncio.to_thread(_write)
```

### 4.2 Invariants that belong in CI

Whichever of §3.1–§3.7 are adopted, these invariants must be enforced by tests:

```python
def test_sell_ladder_never_exceeds_sell_levels():      # P0-1  (shipped)
def test_risk_state_survives_restart():                # P0-2  (shipped)
def test_corrupt_cb_fails_safe_open():                 # P0-2  (shipped)
def test_emergency_handler_signals_shutdown():          # P0-4  (shipped)
def test_policy_receives_fills():                      # P0-5  (shipped)
def test_no_sync_io_on_the_event_loop():                # P0-6  (shipped)
def test_per_bot_equity_is_not_the_account_equity():    # P0-7  TODO
def test_live_atr_is_not_a_synthetic_constant():        # P0-8  TODO
def test_supervisor_slows_ticks_under_pressure():       # P0-9  (shipped)
def test_rate_limit_budget_is_shared_per_exchange():    # P0-10 (shipped, unit level)
def test_promotion_rejects_insufficient_oos_sample():   # P0-11 TODO
def test_promotion_cannot_widen_the_risk_envelope():    # P0-11 TODO
```

---

## 5. System Resilience & Telemetry — recommendations

| Area | Current state | Recommendation |
| :--- | :--- | :--- |
| **Circuit breakers** | Risk CB (correct, now persisted) + SafeMode RAM levels + per-bot stop-loss | Add a **fee-drag breaker**: if `fees_paid / gross_profit` over a rolling window exceeds a threshold, halt new entries. Add an **edge-decay breaker** on realized-vs-expected TP slippage. |
| **Network reconnection** | `_ws_loop` backoff then **permanent REST fallback** (P1-4); adapters retry 3× with exponential backoff | Add a WS **recovery** task: after falling back, re-probe `watch_ticker` on a long interval (e.g. 15 min) and promote back. Emit a metric on degradation. |
| **State persistence / failover** | Atomic JSON + fsync'd JSONL journal per bot; SQLite WAL only in EMERGENCY | Journal is the source of truth — good. Add **rotation/compaction** (P1-5) and document that "Redis/PostgreSQL failover" is **not implemented**; SQLite is used for one emergency flush only. A real failover store is a Stage-3 item. |
| **Logging** | `logging` to stdout, rate-limited error logs (`_note_error`, 1 per key / 5 min) | Good instinct. Move to **structured JSON logs** with `bot_key`, `event`, `order_id`, `tick_ms`. Add a per-tick latency histogram — the single most useful production metric missing today. |
| **Health/telemetry** | `health.json` per bot with ~25 fields incl. regime/Sharpe/Kelly, consumed by dashboard + Zabbix | Add: `tick_ms_p50/p95`, `open_orders`, `rest_calls_per_tick`, `ws_connected`, `equity_guard_hits` (currently only in the backtest!), `fee_drag_pct`, `fill_rate`. The backtest already tracks these; the live path does not. |
| **PnL deviation monitoring** | Not present | Add a reconciliation job: compare `BotState.total_pnl` (journal replay) against exchange-reported fills + balances daily. Any deviation is an accounting bug and must page. |

---

## 6. Validation Checklist for Paper / Live Deployment

**Gate 0 — static (must pass before any run)**
- [x] `ruff check denaro` clean
- [x] Full `denaro/tests` green (223 passed; 4 sandbox-blocked tests verified manually)
- [ ] `config/*.yaml` validated with **unknown keys treated as errors** (`extra='forbid'` on a
      *validation* pass) — closes the P1-6 bug class
- [ ] Every live bot's `fee` matches its actual exchange maker/taker schedule
- [ ] Secret hygiene: keys only via `EnvironmentFile`; a grep for `api_key|secret|passphrase` over
      `config/` returns only placeholders

**Gate 1 — paper, ≥ 72 h continuous**
- [ ] Zero unhandled exceptions in logs; zero `tick error`
- [ ] Invariant `open_ladder_sells <= sell_levels` holds every tick (assert in a monitor)
- [ ] Invariant `open_buys <= levels` holds every tick
- [ ] Tick latency `p95 < 0.25 × tick_interval`; no monotonic growth in `open_orders` or tick time
- [ ] Kill the process twice mid-cycle; on restart: `peak_capital`, `trade_results`,
      `cb.state` preserved; no duplicate orders created
- [ ] Force equity reads out of range; confirm the event loop keeps ticking (heartbeat test)
- [ ] `health.json` fields populated and non-null; `error` field empty or explained

**Gate 2 — live, minimum capital, 2 weeks**
- [ ] Start with the **per-bot ledger** (§3.1) in place — never two bots sharing one unallocated account
- [ ] Verify each bot's `total_equity` independently against the exchange UI
- [ ] Stop-loss drill: trigger `stop_loss_pct` on a tiny position; confirm orders cancelled, asset
      sold, flag persisted, health `blocked`, and **the bot does not re-enter after restart**
- [ ] CB drill: trigger `max_drawdown_limit`; confirm no new orders, and that the daily/weekly
      baselines are unchanged across a restart
- [ ] Emergency drill: simulate `ram > emergency_pct`; confirm orders cancelled **and the node shuts
      down** (this is the P0-4 regression — it silently did not work)
- [ ] Fee reconciliation: `fees_paid` from the journal vs exchange fee report, within 1 %
- [ ] PnL reconciliation: journal-replayed `total_pnl` vs balance delta, within slippage tolerance
- [ ] `fees_over_gross_pct` below the Stage-2 promotion threshold

**Gate 3 — promotion to Stage 2 (100–250 EUR)** — all of:
- [ ] Profit Factor > 1.25 **computed OOS** on ≥ 30 closed cycles, not in-sample
- [ ] Max drawdown < 8 % (MTM, includes inventory)
- [ ] `alpha_vs_hodl_pct` > 0 over the same window
- [ ] Walk-forward verdict `PROMOTE` with `PBO <= 0.25` and `deflated_sharpe > 0` (§3.6)
- [ ] Risk envelope unchanged or strictly tightened by the promotion
- [ ] Order-book gate (§3.2) active, or an explicit written justification for its absence
- [ ] VAGR either disabled, or `on_ohlcv` implemented and `atr_pct` verified non-constant live

**Gate 4 — Stage 3+ (500–1000 EUR), only after Gates 1–3**
- [ ] Pairs/stat-arb enabled **only** with the two-phase commit and per-bot ledger
- [ ] RL/bandit enabled **only** in shadow mode first, with an exploration floor and a regret
      kill-switch
- [ ] A real state store (Postgres/Redis) with tested failover, replacing the JSON/SQLite emergency path

---

## 7. Verification Summary

| Assertion | Evidence | Status |
| :--- | :--- | :--- |
| Ladder duplicated 2 orders/tick | repro `open_sells = [2,4,6,8,10,12]` | fixed, regression test |
| `open_sells` stored `target_price`, grid read `price` | repro printed both key sets | fixed |
| Risk state lost on restart | repro `peak 44→30, trades 6→0` | fixed, regression test |
| `KrakenPermanentError` unbound | repro `hasattr(orch, 'KrakenPermanentError') == False` | fixed, regression test |
| `policy.on_fill` never called | repro counted 0 invocations | fixed, regression test |
| `time` not imported → emergency never shuts down | `ruff F821` | fixed, regression test |
| Override semantics (5 behaviours) | direct execution of all 5 cases | verified pass |
| Full test suite | `pytest denaro/tests` | **223 passed, 0 failed** |
| Lint | `ruff check denaro` | **All checks passed** |
| Overfit promotion risk | `registry.json` `sharpe=-8.137, win_rate=1.0, n_bars=223`; grep: no walk-forward code | documented, blueprint §3.6 |

### Honest disclosure of what was **not** changed

* **P0-7 shared-account equity** — deliberately not patched; blueprint in §3.1. This is the single
  most important remaining item before raising capital.
* **P0-11 promotion governance** — no code written; blueprint in §3.6. Until then, treat
  `config/strategies/registry.json` as **untrusted input** and do not let an optimizer widen
  `stop_loss_pct`, `max_drawdown_limit` or `capital`.
* **P1-3/P0-8 (real OHLCV into the volatility estimators)** — the double-feed and dead kill-switch are
  fixed, but VAGR/`AdaptiveVolGrid` still receive synthetic ±5 bp ranges in live operation. Until
  `on_ohlcv` is implemented for them, **VAGR should not be considered adaptive**.
* **P1-4 WS recovery, P1-5 journal rotation, §3.2–§3.5** — blueprinted, not implemented.

---

## 8. Recommended Execution Order

1. **Merge this change set** (the full P0 fix-set + 23 regression tests). It is independently
   verifiable and every change is covered by a test that fails on the previous revision.
2. **Per-bot capital ledger (§3.1)** and the "no two bots share an unallocated account" rule.
   Blocking for any capital increase.
3. **Promotion governance (§3.6)**. Freeze automated overrides until the walk-forward gate exists.
4. **Edge gate (§3.7)** and **order-book gate (§3.2)** — the cheapest real alpha at this size.
5. **Telemetry**: per-tick latency histogram, `equity_guard_hits`, `fill_rate`, daily PnL
   reconciliation.
6. **MTF regime (§3.3)** + real OHLCV into VAGR; then re-evaluate whether VAGR earns its place.
7. **WS recovery (P1-4)** and **journal rotation (P1-5)**.
8. Only then: **pairs stat-arb (§3.4)**, and **execution bandit in shadow mode (§3.5)**.
