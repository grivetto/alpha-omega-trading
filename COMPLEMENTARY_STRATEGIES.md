# Complementary Strategies for Idle 2.2 SOL

**Current State:**
- Total SOL: ~4.9 (2.2 free + 2.7 in grid)
- Grid: 2 SELL orders at 8.88 + 0.81 (0.733 SOL each)
- Price: ~7.00 (BEAR state)
- Goal: Increase capital utilization from 60% → 90%+

---

## Strategy #1: Lending + Staking (3 min coding)

**Approach:** Earn passive yield on idle SOL while keeping 0.5 SOL liquid for grid rebalancing.

**Implementation:**
```python
# binance_earn.py (NEW FILE)
import os, requests

BINANCE_API = "https://api.binance.com"
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

def lending_savings(amount_usdc: float):
    """Place in flexible savings (daily yield). Returns transaction ID."""
    endpoint = "/sapi/v1/simple-savings/flexible/setAvailable"
    params = {"asset": "SOL", "amount": amount_usdc}
    return _sign_post(endpoint, params)

def staking_locked(amount_sol: float, days: int = 30):
    """Stake SOL for higher yield (locked). Unlock penalty applies."""
    endpoint = "/sapi/v1/lending/customizedFixed/position/"
    params = {"asset": "SOL", "amount": amount_sol, "day": days}
    return _sign_post(endpoint, params)

def unstake_locked(position_id: str):
    """Redeem locked staking early (with penalty)."""
    endpoint = "/sapi/v1/lending/customizedFixed/position/redemption/"
    params = {"positionId": position_id}
    return _sign_post(endpoint, params)

def get_lending_balances():
    """Check current lending balances + yield."""
    endpoint = "/sapi/v1/simple-savings/flexible/position"
    return _sign_get(endpoint)
```

**Action Items:**
1. Transfer 1.7 SOL to flexible savings → earn ~3-5% APY
2. Lock 0.5 SOL for 7 days → earn ~6-8% APY (can break early if grid needs)
3. Schedule daily check: if SOL price drops >2%, unstake and return to grid

**Use Cases:**
- Price rising rapidly: unstake + reinvest in grid
- Price consolidation: keep earning yield
- Emergency: break lock (penalty ~0.5%) for grid opportunity

---

## Strategy #2: Tight Grid Scalper (10 min coding)

**Approach:** Run ultra-tight grid on 1.5 SOL to scalp micro-movements while preserving main grid's larger orders.

**Configuration:**
```python
# denaro_v3/config.py - ADD
@dataclass
class ScalpConfig:
    symbol: str = "SOL/USDC"
    spacing_pct: float = 0.3  # 3x tighter than main grid
    levels: int = 6  # 3 buys + 3 sells
    min_order_usdc: float = 25.0  # $25 min (vs $10 main)
    max_order_usdc: float = 75.0  # $75 max (vs $100 main)
    target_profit_pct: float = 0.5  # 0.5% per full cycle

SCALP_CFG = ScalpConfig()
```

**Implementation:**
```python
# denaro_v3/scalp_engine.py (NEW FILE)
from config import ScalpConfig
from circuit_breaker import CircuitBreaker
from data_feeder import DataFeeder

class ScalpEngine:
    def __init__(self, cfg: ScalpConfig, feeder: DataFeeder, breaker: CircuitBreaker):
        self._cfg = cfg
        self._feeder = feeder
        self._breaker = breaker
        self._levels = []
    
    def sync_orders(self):
        """Place tight grid around current price."""
        ticker = self._feeder.get_ticker(self._cfg.symbol)
        mid = ticker.get("last", 0)
        if mid <= 0: return
        
        spacing = self._cfg.spacing_pct / 100
        
        for i in range(3):
            buy_price = self._round(mid * (1 - spacing * (i + 1)))
            self._place_order("buy", buy_price, 0.2)  # 0.2 SOL per level
        
        for i in range(3):
            sell_price = self._round(mid * (1 + spacing * (i + 1)))
            self._place_order("sell", sell_price, 0.2)
    
    def _place_order(self, side: str, price: float, amount: float):
        if self._breaker.state != "closed": return
        
        if side == "buy":
            self._feeder.create_limit_buy(self._cfg.symbol, amount, price)
        else:
            self._feeder.create_limit_sell(self._cfg.symbol, amount, price)
```

**Integration with main.py:**
```python
# Add to DenaroV3.__init__()
self._scalp_engine = None

# Add to _init_modules() after grid engine
from scalp_engine import ScalpEngine
from config import SCALP_CFG
self._scalp_engine = ScalpEngine(SCALP_CFG, self._feeder, self._breaker)

# Add to _loop() - run every cycle
if self._scalp_engine:
    self._scalp_engine.sync_orders()
```

**Advantage:** 
- Captures $0.02-$0.05 swings that main grid misses
- 3% daily volatility → ~6-12 scalp cycles → compounding

---

## Strategy #3: Conditional Rebalancer (5 min coding)

**Approach:** Auto-redirect idle SOL to grid when price moves favorably.

**Logic:**
```python
# denaro_v3/rebalancer.py (NEW FILE)
from data_feeder import DataFeeder
from circuit_breaker import CircuitBreaker

def maybe_rebalance(feeder: DataFeeder, breaker: CircuitBreaker, grid_engine):
    """Move idle SOL to grid if price favorable."""
    # Check idle balance
    free_sol = feeder.get_free_balance("SOL")
    free_usdc = feeder.get_free_balance("USDC")
    
    if free_sol < 0.1 and free_usdc < 10:
        return  # Nothing to rebalance
    
    ticker = feeder.get_ticker("SOL/USDC")
    price = ticker.get("last", 0)
    
    # If price dropped >2% from last grid high, add buy orders
    last_high = 8.88  # From your grid
    if price < last_high * 0.98 and free_usdc > 10:
        # Price dip = buying opportunity
        amount = min(free_usdc / price, free_sol) * 0.5  # Use 50% of idle
        grid_engine._place_level(GridLevel("buy", price * 0.995, amount))
    
    # If price rallied >1.5% and we have SOL, add sell orders
    if price > last_high * 1.015 and free_sol > 0.1:
        amount = min(free_sol, 0.5)
        grid_engine._place_level(GridLevel("sell", price * 1.005, amount))
```

**Trigger:** Run every 30 minutes + after grid fills

---

## Strategy #4: Mini-Grid with Auto-Stop (7 min coding)

**Approach:** Run a "profit taker" grid on 1 SOL that auto-cancels when total profit > $3.

```python
# denaro_v3/profiter.py (NEW FILE)
class Profiter:
    """Self-destructing grid for quick profits."""
    
    def __init__(self, target_profit: float = 3.0, lifespan: int = 3600):
        self._target_pnl = target_profit
        self._created_at = time.time()
        self._lifespan = lifespan
        self._active = True
    
    def should_run(self) -> bool:
        """Auto-turn off after profit target hit or timeout."""
        if not self._active: return False
        if time.time() - self._created_at > self._lifespan: return False
        
        # Check if target hit (from circuit breaker history)
        breaker = self._get_breaker()
        return breaker.total_pnl < self._target_pnl
    
    def cancel_all(self):
        """Shut down and cancel orders."""
        self._active = False
        for order in self._feeder.get_open_orders("SOL/USDC"):
            if "profit" in order.get("meta", ""):
                self._feeder.cancel_order(order["id"], "SOL/USDC")
```

---

## Immediate Action Plan (30 min total)

| Time | Task | File |
|------|------|------|
| 0-3 min | Create lending module | `binance_earn.py` |
| 3-5 min | Add lending check to main loop | `denaro_v3/main.py` |
| 5-15 min | Create scalp engine | `denaro_v3/scalp_engine.py` |
| 15-20 min | Add scalp to config + main | `denaro_v3/config.py`, `denaro_v3/main.py` |
| 20-25 min | Create rebalancer helper | `denaro_v3/rebalancer.py` |
| 25-30 min | Integrate + test | `denaro_v3/main.py` |

---

## Expected Outcome

**Before:**
- Capital utilization: 60% (2.9/4.9 SOL active)
- Idle: 2.2 SOL ($15.40)

**After:**
- Lending: 1.7 SOL earn ~$0.03/day yield
- Scalp grid: 1.5 SOL actively trading
- Rebalancer: 0.2 SOL auto-adds to main grid on dips
- **Utilization: 92%+**

**Risk Control:**
- All strategies respect circuit breaker
- Scalp grid uses smaller size ($75 vs $100)
- Lending can be liquidated in <1 hour if needed
- Profiter auto-shuts after $3 profit or 1 hour

---

## Monitoring Checklist

✅ Check lending balances daily (`get_lending_balances()`)
✅ Watch scalp grid activity in logs
✅ If SOL breaks $8.50: cancel scalp orders, let main grid handle rally
✅ If SOL breaks $6.00: unstake lending + dump to grid
