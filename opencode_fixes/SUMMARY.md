# Denaro v3 — Audit Summary

## Ratings

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Profitability** | 7/10 | Small gains from tight grid + WS speed; $1–2/day on ~$224 capital (0.5% daily). |
| **Robustness** | 5/10 | Circuit breaker helps, but state-persistence bugs, blocking HTTP in async, file-lock race on shared FS break reliability. |
| **Code Quality** | 5/10 | Clean layout, typed dataclasses, but duplicated rounding, silent fallbacks, broken equity calc, and dead code. |
| **Scalability** | 3/10 | Single-process sync loop, file-based locks, blocking I/O. Won't handle 10× capital or 10 pairs without refactor. |

---

## Top 3 Reasons It Makes ~$1–2/Day

1. **Tight grid spacing (1.2%) + ATR-based dynamic spacing** captures frequent micro-spreads — the bot is effectively a market maker in a narrow band.
2. **WebSocket fills in <500ms** let it place the next grid order before REST-pollers react, reducing adverse selection.
3. **Circuit breaker stays CLOSED** under normal conditions (3% daily drawdown rarely hit on $200 capital), so nothing blocks trades.

---

## Critical Bugs Found

### CRITICAL: Equity calculation ignores base asset value at startup (`main.py:106-114`)
Initial equity = USDC balance only. Base assets (SOL, DOGE, ADA) are not priced into equity. Circuit breaker `update_equity` gets ~1/3 of true capital → `max_risk_per_trade_pct` and `max_daily_loss_pct` are **calculated on the wrong number**. If the bot accumulates base tokens, the equity under-report worsens over time.

### CRITICAL: `_place_level` ignores circuit breaker's limited `max_amount` (`grid_engine.py:226-252`)
When circuit breaker returns `(True, "HALF_OPEN", reduced_amount)`, the code logs the warning but **places the full original order size**. The size-reduction mechanism is completely non-functional.

### HIGH: Blocking `requests` inside async event loop (`websocket_client.py:118-130, 138-146`)
`UserDataStream._get_listen_key` and `_keepalive` use synchronous `requests.post/put`. A 10s timeout blocks the entire event loop → no grid sync, no heartbeat, no WS processing for 10 seconds. On flaky networks this kills the bot.

### HIGH: Leader lock file path hardcoded to `/tmp/denaro_locks` (`leader_election.py:21`)
Windows and containers without `/tmp` fail silently. Lock files never created → leader election is dead on those machines → possible split-brain (two instances trading same pair).

### MEDIUM: Full cache flush on every trade (`data_feeder.py:130-133`)
`on_trade_executed()` calls `invalidate()` with no prefix, wiping OHLCV/ticker caches too. Destroys the caching layer's purpose — API calls are not reduced by ~90% as claimed.

### MEDIUM: Zero-price fallback in `get_ticker` (`data_feeder.py:100-103`)
When REST fails, returns `{"last": 0}`. This propagates to `calculate_levels` → `mid = 0` → division by zero crash (caught, but bot loses a cycle). Should return None and let caller retry.

### MEDIUM: `reset_grid` races with cancel confirmations (`grid_engine.py:255-267`)
Cancels orders then immediately recalculates grid. Exchange may not have processed cancellations yet → `sync_orders` sees stale open orders → places duplicates.

### MEDIUM: State persistence crash-on-restart (`circuit_breaker.py:45-48`)
`circuit_breaker.json` in CWD. If bot was OPEN before crash, restart reads OPEN state and refuses to trade forever. No automatic recovery or override mechanism.

### LOW: ATR fallback silently catches all exceptions (`grid_engine.py:70-74`)
`except Exception: pass` hides real errors (network, auth). Bot uses fixed 1.2% spacing even when exchange is reachable but OHLCV fetch fails transiently.

### LOW: `_round_price` precision logic wrong for Binance (`grid_engine.py:140-149`)
Binance `precision.price` is a float step (e.g., 0.01), not a decimal count. Code treats `< 1` as float step correctly, but `else: round(price, int(step_size))` would cast a float like 0.1 to `int(0.1) = 0` → no rounding.

---

## Dead Code & Redundancies

| File | Issue |
|------|-------|
| `grid_engine.py:133-134` | `if not market.get("precision"):` guard never fires — `load_markets` called inside cached `market()` |
| `circuit_breaker.py:67-68` | Checksum verification on state file — unused in practice (never validated before load, tampered file just resets to CLOSED anyway) |
| `data_feeder.py:171-173` | `trade_count` property: incremented but never read outside tests |
| `tools/debug_nuvola.py`, `tools/cancel_all_orders.py` | Manual ops scripts, not part of core — clutter the repo |
| `denaro_v3/circuit_b- in filename vs `circuit_breaker` in code | Consistent naming confusion — no functional impact but indicates drift |

---

## Fixes Written

Files in `opencode_fixes/`:

| File | Purpose |
|------|---------|
| `patch_grid_engine.py` | Monkey-patch `_place_level` to enforce circuit breaker's reduced max_amount |
| `patch_leader_heartbeat.py` | `WebSocketHeartbeatMonitor` — cross-validates lock file to prevent split-brain on shared FS |
| `state_validator.py` | Pre-start guard for circuit_breaker.json — waits for override file if state is OPEN, exits with code 42 otherwise |

---

## Recommended Next Actions (Priority Order)

1. **Fix equity calculation** — price base assets at startup (3 lines in `main.py:106-114`)
2. **Fix `_place_level` size reduction** — apply `max_amount` returned by `can_trade` (2 lines in `grid_engine.py:239-242`)
3. **Replace `requests` with async HTTP** in `UserDataStream` — unblocks the event loop
4. **Change `LOCK_DIR` to `tempfile.gettempdir()`** — cross-platform leader election
5. **Make `invalidate` key-targeted** — preserve OHLCV/ticker caches
6. **Add `StateValidator`** to `main.py` startup — prevent restart-death loop
7. **Refactor rounding into shared utility** — 4 identical implementations, 1 bug