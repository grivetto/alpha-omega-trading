# FASE 2 Review — auto_gen_1788015743.py
**Date:** 2026-08-29 17:00 UTC
**Reviewers:** MoA (M3 + Nemotron-Ultra-120B + Nemotron-Super-120B)
**Verdict:** ❌ REJECT — 6 blocking bugs, regenerate as v2

## Blocking issues (must fix)

1. **`_regime_vol` is O(N) and recomputes EWMA from scratch every tick.** Docstring claims "O(1) memory per bar, streaming-friendly" — implementation contradicts both. Also computes EWMA on **log prices** (non-stationary) instead of **log returns** → variance is biased and meaningless.
   - Fix: incremental update on each tick, EWMA on `r = log(p_t) - log(p_{t-1})` and on `r²`.
   ```python
   r = self.log_prices[-1] - self.log_prices[-2]
   self._ewma = (1 - alpha) * self._ewma + alpha * r
   self._ewma_var = (1 - alpha) * self._ewma_var + alpha * (r - self._ewma) ** 2
   ```

2. **`on_fill` win-rate is incoherent / dead.** `_n_wins_param` never updated, `_fract_wins` self-assigned as no-op, numerator uses `_fract_wins + 1e-9`, denominator adds 1 unconditionally → win_rate collapses to ~1e-9. Kelly branch is dead. Need real `is_win` notion (round-trip PnL > 0) and incremental `_wins` / `_losses` counters, or pass `is_win: bool` from the engine.

3. **`_build_levels` produces 11 levels then silently drops 1** (`levels[-10:]` on a 11-item list). Either build `2*max_grid_levels` levels symmetrically without slicing, or set `n_levels` per regime (low=3, med=5, high=10) and skip the slice.

4. **`__post_init__` calls `super().__init__(self.config)` before dataclass field assignment finishes** — bypasses `validate_config` on the user-supplied config. Replace dataclass-with-post_init with a normal `__init__(self, config: Config)` or use `InitVar`.

5. **Kelly math is mislabeled + double-counted with grid exposure.** `kelly_b = max(p-0.5, 0.02)` is just `(p - q)` with `b=1`, not Kelly. With `p=0.6` and `kelly_k=0.5`, the cap (`5%`) is binding essentially always. Either compute proper `f* = (b*p - q)/b` with tracked `avg_win / avg_loss`, or rename to "convexity overlay" and cap at 1–2% of capital so it doesn't shadow the grid sizing.

6. **Regime thresholds assume per-bar log-return stddev ~0.01 (1% bars).** A 2% single-bar move is a flash crash, not a "high" regime. Either annualize (`vol * sqrt(periods_per_year)`) or scale thresholds by bar frequency.

## Secondary issues (should fix in v2)

- `log_prices` is a `list` with `del [0:...]` every tick → O(N) shift. Use `collections.deque(maxlen=vol_window+1)`.
- `_chunked_mean` is dead code — drop or repurpose (only useful for offline analytics, not the hot path).
- `_pending` dict is never read — orders need round-trip resolution before `on_fill` can determine win/loss.
- `Config` validation missing for `vol_window`, `atr_window`, `min/max_grid_levels`. `max_grid_levels` should be odd for symmetric halving.
- `_memory_sweep()` defined at module scope, not a method. Call periodically inside `on_tick` (every `chunk_size` ticks) to honor the OOM-safety claim, not just at end of `__main__`.
- Min grid levels (`min_grid_levels`) declared but never enforced.

## v2 acceptance criteria

- [ ] `_regime_vol` updates in O(1) per tick from log-returns, not log prices
- [ ] `on_fill(order_id, price, qty, is_win=None)` — caller can pass win flag, default derived from round-trip PnL if `_pending` is resolved
- [ ] Grid levels are regime-aware and symmetric (no silent drop)
- [ ] `__init__` validates the actual config passed in
- [ ] Kelly math is either properly implemented (b = avg_win/avg_loss) OR explicitly renamed + capped to avoid double-counting with grid notional
- [ ] Regime thresholds scaled to bar frequency (annualize or document the per-bar assumption)
- [ ] Smoke test in `__main__` runs 1000+ ticks, prints regime distribution + final win_rate, asserts `win_rate` is in (0, 1) after at least one fill
- [ ] Memory bounded by `O(vol_window)` regardless of stream length

## Action
Queue v2 directive to DeepSeek with the above as a hard checklist. Do not advance to FASE 3 until v2 passes the same review.
