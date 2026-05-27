"""
markov_regime.py — Markov Regime Detection Module (Hedge Fund Method)

Computes a 3×3 Markov transition matrix (Bull/Bear/Sideways) from OHLCV data.
Based on the "Hedge Fund Method" from the YouTube video:
  - 3 states: Bull, Bear, Sideways
  - N-period return threshold (default: 20 periods, 5%)
  - 3×3 transition matrix with persistence/stickiness diagonal
  - Signal: bull_bear_diff = P(bull_tomorrow) - P(bear_tomorrow)
    → Positive = long bias, magnitude = position sizing
    → Negative = short bias, magnitude = position sizing

Integration: chiamare compute_markov_matrix() e usare markov_signal() per
il ctx dict nelle strategie della squadra.

Dipende solo da: math, statistics (no numpy/statsmodels needed for core).
"""

import math
import statistics
from typing import Optional

# ── Default parameters (standard: 20-period lookback, 5% threshold) ──
DEFAULT_PERIODS = 20       # number of candles for return calculation
DEFAULT_BULL_THRESHOLD = 5.0   # % return to classify as bull
DEFAULT_BEAR_THRESHOLD = -5.0  # % return to classify as bear

# State labels
BULL = "bull"
BEAR = "bear"
SIDEWAYS = "sideways"

STATES = [BULL, BEAR, SIDEWAYS]


def classify_state(return_pct: float,
                   bull_threshold: float = DEFAULT_BULL_THRESHOLD,
                   bear_threshold: float = DEFAULT_BEAR_THRESHOLD) -> str:
    """
    Classify a return as Bull, Bear, or Sideways state.

    Args:
        return_pct: Period return as percentage (e.g., 3.5 = 3.5%)
        bull_threshold: Minimum return % to be Bull (default 5.0)
        bear_threshold: Maximum return % to be Bear (default -5.0)

    Returns:
        "bull", "bear", or "sideways"
    """
    if return_pct >= bull_threshold:
        return BULL
    elif return_pct <= bear_threshold:
        return BEAR
    else:
        return SIDEWAYS


def compute_returns(ohlcv: list, periods: int = DEFAULT_PERIODS,
                    price_field: int = 4) -> list:
    """
    Compute rolling N-period returns from OHLCV data.

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]
        periods: rolling window for return calc (default 20)
        price_field: index of price in candle (4 = close)

    Returns:
        list of return percentages, length = len(ohlcv) - periods
        Each entry: (timestamp, return_pct)
    """
    if len(ohlcv) < periods + 1:
        return []

    closes = [c[price_field] for c in ohlcv]
    returns = []
    for i in range(periods, len(closes)):
        start_price = closes[i - periods]
        end_price = closes[i]
        if start_price > 0:
            ret = (end_price - start_price) / start_price * 100
            returns.append((ohlcv[i][0], ret))
    return returns


def label_states(returns: list,
                 bull_threshold: float = DEFAULT_BULL_THRESHOLD,
                 bear_threshold: float = DEFAULT_BEAR_THRESHOLD) -> list:
    """
    Label each return with its state.

    Args:
        returns: list of (timestamp, return_pct)
        bull_threshold, bear_threshold: state thresholds

    Returns:
        list of (timestamp, return_pct, state)
    """
    return [
        (ts, ret, classify_state(ret, bull_threshold, bear_threshold))
        for ts, ret in returns
    ]


def build_transition_matrix(labels: list) -> dict:
    """
    Build a 3×3 transition count matrix from labeled states.

    Counts transitions: [current_state][next_state]

    Args:
        labels: list of (timestamp, return_pct, state)

    Returns:
        {
            "counts": {
                "bull": {"bull": N, "bear": N, "sideways": N},
                "bear": {...},
                "sideways": {...}
            },
            "probabilities": same shape but normalized to 0..1 per row,
            "total_transitions": int,
            "is_cold_start": bool (True if < 5 transitions)
        }
    """
    # Initialize counts
    counts = {s: {t: 0 for t in STATES} for s in STATES}

    for i in range(len(labels) - 1):
        current = labels[i][2]
        next_s = labels[i + 1][2]
        counts[current][next_s] += 1

    total = sum(counts[s][t] for s in STATES for t in STATES)
    is_cold = total < 5

    # Normalize to probabilities
    probs = {}
    for s in STATES:
        row_total = sum(counts[s].values())
        if row_total > 0:
            probs[s] = {t: round(counts[s][t] / row_total, 4) for t in STATES}
        else:
            probs[s] = {t: 0.0 for t in STATES}

    return {
        "counts": counts,
        "probabilities": probs,
        "total_transitions": total,
        "is_cold_start": is_cold,
    }


def compute_stickiness(matrix: dict) -> dict:
    """
    Extract stickiness (persistence) scores from the transition matrix.

    Stickiness = probability that the state stays the same tomorrow
    (diagonal of the 3×3 matrix).

    Args:
        matrix: output of build_transition_matrix()

    Returns:
        {
            "bull_stickiness": float (0..1),
            "bear_stickiness": float (0..1),
            "sideways_stickiness": float (0..1),
            "avg_stickiness": float,
            "most_sticky": "bull"|"bear"|"sideways"
        }
    """
    probs = matrix["probabilities"]
    stickiness = {}
    for s in STATES:
        stickiness[s] = probs[s][s]

    # Determine most sticky
    most = max(stickiness, key=stickiness.get)
    avg = statistics.mean(stickiness.values()) if stickiness else 0.0

    return {
        "bull_stickiness": round(stickiness.get(BULL, 0), 4),
        "bear_stickiness": round(stickiness.get(BEAR, 0), 4),
        "sideways_stickiness": round(stickiness.get(SIDEWAYS, 0), 4),
        "avg_stickiness": round(avg, 4),
        "most_sticky": most,
    }


def markov_signal(matrix: dict, current_state: Optional[str] = None) -> dict:
    """
    Generate a trading signal from the Markov transition matrix.

    Core formula (from the video):
        bull_bear_diff = P(bull_tomorrow) - P(bear_tomorrow)
        - Positive → long bias (size proportional to magnitude)
        - Negative → short bias

    Args:
        matrix: output of build_transition_matrix()
        current_state: current regime state. If None, derives from the
                       matrix's most recent state (last known).

    Returns:
        {
            "bull_bear_diff": float      (-1..+1, signal strength)
            "bull_prob": float            P(bull tomorrow)
            "bear_prob": float            P(bear tomorrow)
            "sideways_prob": float        P(sideways tomorrow)
            "current_state": str          "bull"|"bear"|"sideways"
            "signal_type": str            "long"|"short"|"neutral"
            "persistence": float          0..1 (how strong the trend is)
        }
    """
    probs = matrix["probabilities"]

    if current_state is None:
        # If no current state provided, use the state with highest
        # overall probability (stationary-like approximation)
        state_probs = {}
        for s in STATES:
            # Sum of transition probabilities weighted by count
            total_prob = sum(probs[s].values())
            state_probs[s] = total_prob
        if not state_probs or all(p == 0 for p in state_probs.values()):
            current_state = SIDEWAYS  # fallback
        else:
            current_state = max(state_probs, key=state_probs.get)

    # Get transition probabilities from current state
    row = probs.get(current_state, {})
    bull_p = row.get(BULL, 0.0)
    bear_p = row.get(BEAR, 0.0)
    side_p = row.get(SIDEWAYS, 0.0)

    # Bull-bear differential
    diff = round(bull_p - bear_p, 4)

    # Signal type
    if diff >= 0.15:
        sig_type = "long"
    elif diff <= -0.15:
        sig_type = "short"
    else:
        sig_type = "neutral"

    # Persistence = how likely the current state persists
    persistence = row.get(current_state, 0.0)

    return {
        "bull_bear_diff": diff,
        "bull_prob": round(bull_p, 4),
        "bear_prob": round(bear_p, 4),
        "sideways_prob": round(side_p, 4),
        "current_state": current_state,
        "signal_type": sig_type,
        "persistence": round(persistence, 4),
    }


def matrix_power(probs: dict, power: int) -> dict:
    """
    Raise the transition matrix to a power (multi-step forecast).
    Uses basic matrix multiplication.

    For power=2: 2-day forecast. For power=3: 3-day forecast, etc.
    As power increases, probabilities converge toward stationary
    distribution.

    Args:
        probs: {state: {state: prob}} from build_transition_matrix()
        power: exponent (1 = tomorrow, 2 = in 2 days, etc.)

    Returns:
        Same shape as probs but for the N-day-ahead forecast.
    """
    if power <= 1:
        return probs

    # Convert to list of lists for easy multiplication
    # Order: [bull, bear, sideways]
    idx = {BULL: 0, BEAR: 1, SIDEWAYS: 2}
    rev = {0: BULL, 1: BEAR, 2: SIDEWAYS}

    # Build matrix as 3×3 list
    m = [[0.0] * 3 for _ in range(3)]
    for s in STATES:
        for t in STATES:
            m[idx[s]][idx[t]] = probs[s][t]

    # Multiply by itself 'power' times
    result = [row[:] for row in m]
    for _ in range(power - 1):
        new = [[0.0] * 3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                s = sum(result[i][k] * m[k][j] for k in range(3))
                new[i][j] = round(s, 6)
        result = new

    # Convert back to dict
    result_dict = {}
    for i in range(3):
        s = rev[i]
        result_dict[s] = {}
        for j in range(3):
            t = rev[j]
            result_dict[s][t] = result[i][j]

    return result_dict


def stationary_distribution(probs: dict, precision: float = 0.0001,
                            max_iter: int = 1000) -> dict:
    """
    Compute the stationary distribution of the Markov chain.
    The long-run probability of being in each state, regardless of
    starting state.

    Uses power iteration (multiply matrix by itself until convergence).

    Args:
        probs: {state: {state: prob}}
        precision: convergence threshold
        max_iter: safety limit

    Returns:
        {"bull": float, "bear": float, "sideways": float}
    """
    current = probs
    for _ in range(max_iter):
        next_m = matrix_power(current, 2)
        # Check convergence: max difference < precision
        converged = True
        for s in STATES:
            for t in STATES:
                if abs(next_m[s][t] - current[s][t]) > precision:
                    converged = False
                    break
            if not converged:
                break
        if converged:
            # Pick any row (all converge to same stationary dist)
            return {s: round(next_m[BULL][s], 4) for s in STATES}
        current = next_m

    # Return best approximation
    return {s: round(current[BULL][s], 4) for s in STATES}


def compute_markov_matrix(ohlcv: list,
                          periods: int = DEFAULT_PERIODS,
                          bull_threshold: float = DEFAULT_BULL_THRESHOLD,
                          bear_threshold: float = DEFAULT_BEAR_THRESHOLD,
                          price_field: int = 4,
                          return_matrix: bool = True,
                          return_stickiness: bool = True,
                          return_signal: bool = True,
                          return_forecast: int = 0,
                          return_stationary: bool = False) -> dict:
    """
    Complete Markov regime analysis pipeline.

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]
        periods: rolling window for state classification (default 20)
        bull_threshold: % return threshold for bull (default 5.0)
        bear_threshold: % return threshold for bear (default -5.0)
        price_field: index of close price in candle (4)
        return_matrix: include transition matrix in output
        return_stickiness: include stickiness scores
        return_signal: include trading signal (bull_bear_diff)
        return_forecast: if > 0, compute N-day-ahead forecast matrix
        return_stationary: include long-run stationary distribution

    Returns:
        dict with requested fields, or {"error": "..."} on failure
    """
    if not ohlcv or len(ohlcv) < periods + 2:
        return {
            "error": f"need at least {periods + 2} candles, got {len(ohlcv) if ohlcv else 0}",
            "is_cold_start": True,
        }

    # 1. Compute rolling returns
    returns = compute_returns(ohlcv, periods, price_field)
    if len(returns) < 2:
        return {"error": "insufficient returns", "is_cold_start": True}

    # 2. Label states
    labels = label_states(returns, bull_threshold, bear_threshold)

    # 3. Build transition matrix
    matrix = build_transition_matrix(labels)

    result = {
        "symbol": None,  # caller can fill this
        "last_price": ohlcv[-1][price_field],
        "last_return": round(returns[-1][1], 4) if returns else 0.0,
        "last_state": labels[-1][2] if labels else SIDEWAYS,
        "total_candles": len(ohlcv),
        "labeled_periods": len(labels),
        "is_cold_start": matrix["is_cold_start"],
    }

    # Include state history (last 5 for reference)
    result["recent_states"] = [
        {"timestamp": ts, "return_pct": round(ret, 2), "state": st}
        for ts, ret, st in labels[-10:]
    ]

    if return_matrix:
        result["matrix"] = {
            "counts": matrix["counts"],
            "probabilities": matrix["probabilities"],
            "total_transitions": matrix["total_transitions"],
        }

    if return_stickiness:
        result["stickiness"] = compute_stickiness(matrix)

    if return_signal:
        current_state = labels[-1][2] if labels else None
        result["signal"] = markov_signal(matrix, current_state)

    if return_forecast > 1:
        result[f"forecast_{return_forecast}d"] = matrix_power(
            matrix["probabilities"], return_forecast
        )

    if return_stationary:
        result["stationary"] = stationary_distribution(matrix["probabilities"])

    return result


# ── Convenience: scale thresholds by candle interval ──────────

def scale_thresholds_for_timeframe(timeframe: str) -> dict:
    """
    Scale Bull/Bear thresholds based on candle interval.

    The standard 5% threshold is for daily candles (20d return).
    For shorter timeframes, scale proportionally.

    Args:
        timeframe: "1m", "5m", "15m", "1h", "4h", "1d"

    Returns:
        {"periods": int, "bull_threshold": float, "bear_threshold": float}
    """
    # Daily is the baseline: 20 periods, 5%
    minutes_per_candle = {
        "1m": 1, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "6h": 360,
        "12h": 720, "1d": 1440,
    }

    mins = minutes_per_candle.get(timeframe, 1440)
    scale = mins / 1440  # fraction of a day

    # Scale: shorter timeframe → smaller thresholds, fewer periods
    if scale < 0.01:  # < 15min candles
        periods = 48   # look back more candles
        threshold = 5.0 * scale * 48  # adjust
    elif scale < 0.1:  # 15min - 2h
        periods = 20
        threshold = 5.0 * scale * 20
    else:
        periods = 20
        threshold = 5.0

    # Reasonable minimums
    periods = max(periods, 10)
    threshold = max(threshold, 0.5)

    return {
        "periods": periods,
        "bull_threshold": round(threshold, 2),
        "bear_threshold": round(-threshold, 2),
    }


# ── Bot integration helpers ──────────────────────────────────

def markov_confidence_modifier(markov_result: dict) -> float:
    """
    Convert Markov regime signal into a score modifier for bot strategies.

    Returns a value between -0.3 and +0.3 that can be added to the bot's
    existing score (RSI, volume, etc.) to incorporate regime context.

    Rules:
      - bull_bear_diff >= 0.5  → +0.3 (strong bull regime → boost buys)
      - bull_bear_diff >= 0.2  → +0.15 (moderate bull)
      - bull_bear_diff <= -0.5 → -0.3 (strong bear → suppress buys)
      - bull_bear_diff <= -0.2 → -0.15 (moderate bear)
      - otherwise → 0.0 (neutral regime, no modification)

    If cold start (not enough data) → 0.0

    Args:
        markov_result: output of compute_markov_matrix()

    Returns:
        float between -0.3 and +0.3
    """
    if not markov_result:
        return 0.0

    if markov_result.get("is_cold_start", False):
        return 0.0

    signal = markov_result.get("signal")
    if not signal:
        return 0.0

    diff = signal.get("bull_bear_diff", 0.0)

    if diff >= 0.5:
        return 0.30
    elif diff >= 0.2:
        return 0.15
    elif diff <= -0.5:
        return -0.30
    elif diff <= -0.2:
        return -0.15
    else:
        return 0.0


def markov_position_sizing_factor(markov_result: dict,
                                  base_factor: float = 1.0,
                                  max_factor: float = 1.5,
                                  min_factor: float = 0.3) -> float:
    """
    Convert Markov regime signal into a position-sizing multiplier.

    When bull_bear_diff is strongly positive → increase position size.
    When strongly negative → decrease position size (or avoid entirely).

    Args:
        markov_result: output of compute_markov_matrix()
        base_factor: default multiplier (1.0)
        max_factor: max multiplier for extreme bull (1.5)
        min_factor: min multiplier for extreme bear (0.3)

    Returns:
        float factor to multiply position size by
    """
    if not markov_result or markov_result.get("is_cold_start", False):
        return base_factor

    signal = markov_result.get("signal")
    if not signal:
        return base_factor

    diff = signal.get("bull_bear_diff", 0.0)

    # Map diff [-1, +1] → factor [min_factor, max_factor]
    # Linear interpolation
    factor = base_factor + (diff * (max_factor - base_factor))
    return max(min_factor, min(max_factor, factor))
