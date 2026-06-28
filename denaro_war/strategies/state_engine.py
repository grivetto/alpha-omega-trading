"""State Engine — Hedge fund method: classify market state, predict transitions."""
import time
from datetime import datetime, timedelta

class StateEngine:
    """Hedge Fund State Classifier based on Lewis Jackson / Roan quant method.
    
    Concepts:
    1. States: BULL (>+5% in 20d), BEAR (<-5%), SIDEWAYS (between)
    2. Markov: future depends on current state, not past
    3. Transition Matrix: track all 9 state changes, predict probability
    4. Stickiness: current state most likely to continue
    """
    
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    
    def __init__(self, lookback_days: int = 20, threshold_pct: float = 5.0):
        self.lookback = lookback_days
        self.threshold = threshold_pct / 100  # 5% = 0.05
        self._history: list[str] = []  # daily states
        self._transitions: dict = {}   # "BULL->BULL": count
        self._current_state = self.SIDEWAYS
        self._last_price = 0.0
        self._price_20d_ago = 0.0
        self._last_day_check = ""
    
    def classify(self, current_price: float, ohlcv_20d: list) -> str:
        """Classify current market state based on 20-day price change.
        
        ohlcv_20d: list of [timestamp, open, high, low, close, volume] for ~20 days
        Returns: BULL, BEAR, or SIDEWAYS
        """
        if not ohlcv_20d or len(ohlcv_20d) < 5:
            return self.SIDEWAYS
        
        # Get price from 20 days ago vs now
        price_old = float(ohlcv_20d[0][4])  # close of first candle
        change = (current_price - price_old) / price_old
        
        if change > self.threshold:
            return self.BULL
        elif change < -self.threshold:
            return self.BEAR
        return self.SIDEWAYS
    
    def update(self, current_price: float, ohlcv_daily: list) -> dict:
        """Run daily update. Returns state info for strategy selection."""
        state = self.classify(current_price, ohlcv_daily)
        
        # Track transition
        if self._current_state and self._current_state != state:
            key = f"{self._current_state}->{state}"
            self._transitions[key] = self._transitions.get(key, 0) + 1
        
        old_state = self._current_state
        self._current_state = state
        
        # Calculate transition probabilities
        probs = self._transition_probabilities()
        
        return {
            "state": state,
            "previous": old_state,
            "changed": old_state != state,
            "stickiness": self._stickiness(),
            "next_state_prob": probs.get(state, {}),
            "transition_count": sum(self._transitions.values()),
        }
    
    def _transition_probabilities(self) -> dict:
        """Calculate probability of next state for each current state."""
        if not self._transitions:
            return {}
        probs = {}
        for state in [self.BULL, self.BEAR, self.SIDEWAYS]:
            total = sum(v for k, v in self._transitions.items() if k.startswith(state))
            if total > 0:
                probs[state] = {}
                for target in [self.BULL, self.BEAR, self.SIDEWAYS]:
                    key = f"{state}->{target}"
                    probs[state][target] = self._transitions.get(key, 0) / total
        return probs
    
    def _stickiness(self) -> float:
        """How likely is current state to continue? 0-1."""
        total = sum(self._transitions.values())
        if total == 0:
            return 0.5
        same = self._transitions.get(f"{self._current_state}->{self._current_state}", 0)
        return same / total if total > 0 else 0.5
    
    def strategy_signal(self) -> dict:
        """Return concrete trading signals based on state."""
        s = self._current_state
        if s == self.BULL:
            return {
                "primary": "momentum_long",
                "grid": False,
                "scalper": False,
                "whale": True,
                "sizing": 1.0,  # Full size
                "hold_time": 3600,  # Hold up to 1 hour
            }
        elif s == self.BEAR:
            return {
                "primary": "stay_out",
                "grid": False,
                "scalper": True,  # Only scalp bounces
                "whale": False,
                "sizing": 0.3,  # 30% size max
                "hold_time": 120,  # Quick exits
            }
        else:  # SIDEWAYS
            return {
                "primary": "grid",
                "grid": True,
                "scalper": True,
                "whale": True,
                "sizing": 0.5,
                "hold_time": 600,
            }
    
    @property
    def state(self) -> str:
        return self._current_state
    
    @property
    def history(self) -> list:
        return self._history[-50:] if self._history else []
