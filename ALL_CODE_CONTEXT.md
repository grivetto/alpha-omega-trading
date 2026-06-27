# DENARO ALL VERSIONS - CONTEXT FOR v6


============================================================
# FILE: v3_circuit_breaker.py
============================================================
1|"""Denaro v3 Circuit Breaker — Unified pre-trade risk control.
2|
3|Interrogato PRIMA di ogni trade. Se il circuito è aperto,
4|NESSUN ordine viene piazzato. Protegge il capitale a livello di core.
5|"""
6|
7|import json
8|import os
9|import hashlib
10|import tempfile
11|from dataclasses import dataclass
12|from datetime import datetime, timezone
13|from typing import List
14|
15|from loguru import logger
16|
17|from config import RiskConfig
18|
19|
20|@dataclass
21|class TradeRecord:
22|    """Immutable trade record for P&L tracking."""
23|    timestamp: float
24|    symbol: str
25|    side: str  # 'buy' or 'sell'
26|    amount: float
27|    price: float
28|    pnl: float = 0.0  # Realized P&L in quote currency
29|    fee: float = 0.0
30|
31|
32|class CircuitBreaker:
33|    """Global risk controller. One instance per process.
34|
35|    States:
36|    - CLOSED: Trading allowed (normal operation)
37|    - HALF_OPEN: Reduced position size (-50%)
38|    - OPEN: ALL trading blocked
39|    """
40|
41|    STATE_CLOSED = "closed"
42|    STATE_HALF_OPEN = "half_open"
43|    STATE_OPEN = "open"
44|
45|    def __init__(self, config: RiskConfig, state_file: str = "circuit_breaker.json"):
46|        self._config = config
47|        self._state_file = state_file
48|        self._state = self.STATE_CLOSED
49|        self._reason = ""
50|        self._trades: List[TradeRecord] = []
51|        self._peak_equity: float = 0.0
52|        self._current_equity: float = 0.0
53|        self._consecutive_losses: int = 0
54|        self._daily_pnl: float = 0.0
55|        self._daily_date: str = ""
56|        self._total_pnl: float = 0.0
57|        self._state_since: float = 0.0  # timestamp of last state change
58|        self._load_state()
59|
60|    # ── State Persistence ──────────────────────────────────
61|    def _load_state(self):
62|        """Load persisted circuit breaker state with checksum verification."""
63|        if not os.path.exists(self._state_file):
64|            return
65|        try:
66|            with open(self._state_file) as f:
67|                data = json.load(f)
68|            # Verify checksum
69|            stored_hash = data.pop("_checksum", "")
70|            computed = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
71|            if stored_hash != computed:
72|                logger.warning("Circuit breaker state corrupted — resetting to CLOSED")
73|                self._state = self.STATE_CLOSED
74|                return
75|            self._state = data.get("state", self.STATE_CLOSED)
76|            self._reason = data.get("reason", "")
77|            self._peak_equity = data.get("peak_equity", 0.0)
78|            self._total_pnl = data.get("total_pnl", 0.0)
79|            self._consecutive_losses = data.get("consecutive_losses", 0)
80|        except Exception as e:
81|            logger.error(f"Failed to load circuit breaker state: {e}")
82|            self._state = self.STATE_CLOSED
83|
84|    def _save_state(self):
85|        """Atomically persist circuit breaker state."""
86|        data = {
87|            "state": self._state,
88|            "reason": self._reason,
89|            "peak_equity": self._peak_equity,
90|            "total_pnl": self._total_pnl,
91|            "consecutive_losses": self._consecutive_losses,
92|            "updated": datetime.now(timezone.utc).isoformat(),
93|        }
94|        checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
95|        data["_checksum"] = checksum
96|        try:
97|            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self._state_file) or ".")
98|            with os.fdopen(fd, "w") as f:
99|                json.dump(data, f, indent=2)
100|            os.replace(tmp, self._state_file)
101|        except Exception as e:
102|            logger.error(f"Failed to save circuit breaker state: {e}")
103|
104|    # ── Risk Checks ────────────────────────────────────────
105|    def update_equity(self, total_usdc: float):
106|        """Update current equity. Called every loop cycle."""
107|        self._current_equity = total_usdc
108|        if total_usdc > self._peak_equity:
109|            self._peak_equity = total_usdc
110|        self._check_daily_reset()
111|        self._evaluate()
112|
113|    def _check_daily_reset(self):
114|        """Reset daily P&L counter at midnight UTC."""
115|        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
116|        if today != self._daily_date:
117|            self._daily_pnl = 0.0
118|            self._daily_date = today
119|            logger.info("Daily P&L reset")
120|
121|    def _evaluate(self):
122|        """Evaluate all risk conditions. Most severe wins."""
123|        reasons = []
124|
125|        # L3: Total drawdown > max_drawdown_pct
126|        if self._peak_equity > 0:
127|            drawdown = (self._peak_equity - self._current_equity) / self._peak_equity * 100
128|            if drawdown > self._config.max_drawdown_pct:
129|                reasons.append(f"Drawdown {drawdown:.1f}% > {self._config.max_drawdown_pct}%")
130|
131|        # L2: Daily loss > max_daily_loss_pct
132|        if self._peak_equity > 0:
133|            daily_loss_pct = abs(self._daily_pnl) / self._peak_equity * 100
134|            if self._daily_pnl < 0 and daily_loss_pct > self._config.max_daily_loss_pct:
135|                reasons.append(f"Daily loss {daily_loss_pct:.1f}% > {self._config.max_daily_loss_pct}%")
136|
137|        # L1: Consecutive losses
138|        if self._consecutive_losses >= self._config.max_consecutive_losses:
139|            reasons.append(f"Consecutive losses: {self._consecutive_losses} >= {self._config.max_consecutive_losses}")
140|
141|        if reasons:
142|            # Daily loss or drawdown = full stop. Consecutive losses only = half.
143|            if any("Daily loss" in r or "Drawdown" in r for r in reasons):
144|                self._transition(self.STATE_OPEN, "; ".join(reasons))
145|            else:
146|                self._transition(self.STATE_HALF_OPEN, "; ".join(reasons))
147|        elif self._state != self.STATE_CLOSED:
148|            # Recover: if we're in half_open and have a winning trade, go back
149|            if self._consecutive_losses == 0:
150|                self._transition(self.STATE_CLOSED, "Recovered — no active risk conditions")
151|            # Auto-recovery: force CLOSED after 4h in HALF_OPEN to prevent permanent deadlock
152|            elif self._state == self.STATE_HALF_OPEN and self._state_since > 0:
153|                import time as _time
154|                if _time.time() - self._state_since > 14400:
155|                    logger.warning("Circuit breaker: HALF_OPEN timeout (4h) — forcing CLOSED")
156|                    self._transition(self.STATE_CLOSED, "Auto-recovery timeout")
157|
158|    def _transition(self, new_state: str, reason: str):
159|        """Transition to a new state. Only escalates, never downgrades silently."""
160|        if new_state != self._state:
161|            import time as _time
162|            logger.warning(f"Circuit breaker: {self._state} → {new_state} | {reason}")
163|            self._state = new_state
164|            self._reason = reason
165|            self._state_since = _time.time()
166|            self._save_state()
167|
168|    # ── Pre-Trade Check ────────────────────────────────────
169|    def can_trade(self, amount_usdc: float) -> tuple[bool, str, float]:
170|        """Check if a trade is allowed. Returns (allowed, reason, max_amount).
171|
172|        Called BEFORE every order placement.
173|        """
174|        if self._state == self.STATE_OPEN:
175|            return False, f"CIRCUIT OPEN: {self._reason}", 0.0
176|
177|        if self._state == self.STATE_HALF_OPEN:
178|            reduced = amount_usdc * (self._config.reduced_size_pct / 100.0)
179|            return True, "HALF_OPEN: reduced size", reduced
180|
181|        # VaR check (simplified: risk per trade)
182|        max_risk = self._current_equity * (self._config.max_risk_per_trade_pct / 100.0)
183|        if amount_usdc > max_risk * 2:  # 2x because grid has both sides
184|            return True, "CLOSED", min(amount_usdc, max_risk * 2)
185|
186|        return True, "CLOSED", amount_usdc
187|
188|    # ── Trade Recording ────────────────────────────────────
189|    def record_trade(self, trade: TradeRecord):
190|        """Record a completed trade for P&L tracking."""
191|        self._trades.append(trade)
192|        self._total_pnl += trade.pnl
193|        self._daily_pnl += trade.pnl
194|
195|        if trade.pnl < 0:
196|            self._consecutive_losses += 1
197|        else:
198|            self._consecutive_losses = 0
199|
200|        # Keep only last 1000 trades in memory
201|        if len(self._trades) > 1000:
202|            self._trades = self._trades[-500:]
203|
204|        self._save_state()
205|        self._evaluate()
206|
207|    # ── Properties ─────────────────────────────────────────
208|    @property
209|    def state(self) -> str:
210|        return self._state
211|
212|    @property
213|    def reason(self) -> str:
214|        return self._reason
215|
216|    @property
217|    def peak_equity(self) -> float:
218|        return self._peak_equity
219|
220|    @property
221|    def total_pnl(self) -> float:
222|        return self._total_pnl
223|
224|    @property
225|    def daily_pnl(self) -> float:
226|        return self._daily_pnl
227|
228|    @property
229|    def consecutive_losses(self) -> int:
230|        return self._consecutive_losses
231|
232|    @property
233|    def drawdown_pct(self) -> float:
234|        if self._peak_equity > 0:
235|            return (self._peak_equity - self._current_equity) / self._peak_equity * 100
236|        return 0.0
237|
238|    def summary(self) -> dict:
239|        """Human-readable state summary for logging."""
240|        return {
241|            "state": self._state,
242|            "peak": round(self._peak_equity, 2),
243|            "equity": round(self._current_equity, 2),
244|            "drawdown_pct": round(self.drawdown_pct, 2),
245|            "daily_pnl": round(self._daily_pnl, 2),
246|            "total_pnl": round(self._total_pnl, 2),
247|            "consecutive_losses": self._consecutive_losses,
248|        }
249|

============================================================
# FILE: v3_data_feeder.py
============================================================
1|"""Denaro v3 Data Feeder — Cached API access layer.
2|
3|Fetch ONCE, serve MANY. Invalidate only when necessary.
4|Single entry point for ALL exchange data. Reduces API calls by ~90%.
5|"""
6|
7|import time
8|from typing import Dict, List, Optional, Any
9|from loguru import logger
10|
11|from config import APIConfig
12|
13|
14|class DataFeeder:
15|    """Cached wrapper around ccxt exchange. One fetch = N reads."""
16|
17|    def __init__(self, exchange, config: APIConfig):
18|        self._exchange = exchange
19|        self._config = config
20|        self._cache: Dict[str, tuple[float, Any]] = {}
21|        self._trade_count: int = 0  # Incremented after each fill
22|        self._ws_ticker: Dict[str, dict] = {}  # WebSocket-injected tickers
23|        self._ws_balance: dict = {}  # WebSocket-injected balances
24|
25|    def _get(self, key: str, ttl: int) -> Optional[Any]:
26|        """Return cached value if not expired."""
27|        if key in self._cache:
28|            timestamp, value = self._cache[key]
29|            if time.time() - timestamp < ttl:
30|                return value
31|        return None
32|
33|    def _set(self, key: str, value: Any):
34|        """Store value in cache."""
35|        self._cache[key] = (time.time(), value)
36|
37|    def invalidate(self, prefix: str = ""):
38|        """Remove all cached entries matching prefix. Called after trades."""
39|        if prefix:
40|            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(prefix)}
41|        else:
42|            self._cache.clear()
43|
44|    # ── Balance ────────────────────────────────────────────
45|    def get_balance(self) -> Dict[str, Dict[str, float]]:
46|        """Fetch balance once per cycle. Invalidate after trade."""
47|        key = "balance"
48|        cached = self._get(key, self._config.cache_ttl_balance)
49|        if cached is not None:
50|            return cached
51|        try:
52|            balance = self._exchange.fetch_balance()
53|            self._set(key, balance)
54|            return balance
55|        except Exception as e:
56|            logger.error(f"Balance fetch failed: {e}")
57|            return self._get(key, 99999) or {"free": {}, "used": {}, "total": {}}
58|
59|    def get_free_balance(self, asset: str) -> float:
60|        """Return free balance for a specific asset."""
61|        balance = self.get_balance()
62|        return float(balance.get(asset, {}).get("free", 0) or 0)
63|
64|    def get_total_balance(self, asset: str) -> float:
65|        """Return total (free + locked) balance for a specific asset."""
66|        balance = self.get_balance()
67|        return float(balance.get(asset, {}).get("total", 0) or 0)
68|
69|    # ── OHLCV ──────────────────────────────────────────────
70|    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[List[float]]:
71|        """Fetch OHLCV with caching. Used by grid + indicators."""
72|        key = f"ohlcv:{symbol}:{timeframe}:{limit}"
73|        ttl = self._config.cache_ttl_ohlcv if timeframe in ("1h", "4h") else 120
74|        cached = self._get(key, ttl)
75|        if cached is not None:
76|            return cached
77|        try:
78|            ohlcv = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
79|            self._set(key, ohlcv)
80|            return ohlcv
81|        except Exception as e:
82|            logger.error(f"OHLCV fetch failed for {symbol}: {e}")
83|            return self._get(key, 99999) or []
84|
85|    # ── Ticker ─────────────────────────────────────────────
86|    def get_ticker(self, symbol: str) -> Optional[dict]:
87|        """Fetch ticker with short cache. WebSocket data overrides cache."""
88|        # Check injected WS ticker first (real-time, bypasses cache)
89|        ws_ticker = self._ws_ticker.get(symbol, {})
90|        if ws_ticker and ws_ticker.get("last", 0) > 0:
91|            return ws_ticker
92|
93|        key = f"ticker:{symbol}"
94|        cached = self._get(key, self._config.cache_ttl_ticker)
95|        if cached is not None:
96|            return cached
97|        try:
98|            ticker = self._exchange.fetch_ticker(symbol)
99|            self._set(key, ticker)
100|            return ticker
101|        except Exception as e:
102|            logger.error(f"Ticker fetch failed for {symbol}: {e}")
103|            return self._get(key, 60) or {"last": 0}
104|
105|    def inject_ws_ticker(self, symbol: str, data: dict):
106|        """Inject WebSocket ticker data. Overrides REST cache."""
107|        self._ws_ticker[symbol] = data
108|
109|    def inject_ws_balance(self, balances: dict):
110|        """Inject WebSocket balance update. Invalidates balance cache."""
111|        self._ws_balance = balances
112|        self.invalidate("balance")
113|
114|    # ── Open Orders ────────────────────────────────────────
115|    def get_open_orders(self, symbol: str) -> List[dict]:
116|        """Fetch open orders. Short TTL, invalidated after trade."""
117|        key = f"orders:{symbol}"
118|        cached = self._get(key, self._config.cache_ttl_orders)
119|        if cached is not None:
120|            return cached
121|        try:
122|            orders = self._exchange.fetch_open_orders(symbol)
123|            self._set(key, orders)
124|            return orders
125|        except Exception as e:
126|            logger.error(f"Open orders fetch failed for {symbol}: {e}")
127|            return []
128|
129|    def on_trade_executed(self):
130|        """Called after any order fill. Invalidates balance + orders cache."""
131|        self._trade_count += 1
132|        self.invalidate("balance")
133|        self.invalidate("orders")
134|
135|    # ── Order Execution ────────────────────────────────────
136|    def create_limit_buy(self, symbol: str, amount: float, price: float) -> Optional[dict]:
137|        """Place a limit buy order. Returns order dict or None."""
138|        try:
139|            order = self._exchange.create_limit_buy_order(symbol, amount, price)
140|            self.on_trade_executed()
141|            return order
142|        except Exception as e:
143|            logger.error(f"Limit buy failed: {e}")
144|            return None
145|
146|    def create_limit_sell(self, symbol: str, amount: float, price: float) -> Optional[dict]:
147|        """Place a limit sell order. Returns order dict or None."""
148|        try:
149|            order = self._exchange.create_limit_sell_order(symbol, amount, price)
150|            self.on_trade_executed()
151|            return order
152|        except Exception as e:
153|            logger.error(f"Limit sell failed: {e}")
154|            return None
155|
156|    def cancel_order(self, order_id: str, symbol: str) -> bool:
157|        """Cancel an open order."""
158|        try:
159|            self._exchange.cancel_order(order_id, symbol)
160|            self.on_trade_executed()
161|            return True
162|        except Exception as e:
163|            logger.error(f"Cancel order failed: {e}")
164|            return False
165|
166|    @property
167|    def exchange(self):
168|        """Direct exchange access (use sparingly)."""
169|        return self._exchange
170|
171|    @property
172|    def trade_count(self) -> int:
173|        return self._trade_count
174|

============================================================
# FILE: v5_engine.py
============================================================
1|import hmac
2|import hashlib
3|import time
4|import requests
5|import json
6|import os
7|from typing import Dict, Optional, Tuple
8|from urllib.parse import urlencode
9|
10|
11|class BinanceEngine:
12|    def __init__(self, config_path: str = "config/war_config.json"):
13|        with open(config_path, "r") as f:
14|            self.config = json.load(f)
15|        
16|        # Load API keys from env FIRST, then config fallback
17|        self._load_env_file()
18|        
19|        binance_cfg = self.config.get("binance", {}) or self.config.get("exchanges", {}).get("binance", {})
20|        self.base_url = binance_cfg.get("base_url", "https://api.binance.com")
21|        self.api_key = os.environ.get("BINANCE_API_KEY", "") or binance_cfg.get("api_key", "")
22|        self.api_secret = (os.environ.get("BINANCE_API_SECRET", "") or binance_cfg.get("api_secret", "")).encode()
23|        
24|        self.session = requests.Session()
25|        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
26|        # Default timeout for all requests (connect=5s, read=10s)
27|        self._timeout = (5, 10)
28|
29|    def _load_env_file(self):
30|        """Load .env file into os.environ (systemd EnvironmentFile fallback)."""
31|        import os as _os
32|        env_path = _os.path.join(_os.path.dirname(__file__), "..", ".env")
33|        if _os.path.exists(env_path):
34|            with open(env_path) as f:
35|                for line in f:
36|                    line = line.strip()
37|                    if line and not line.startswith("#") and "=" in line:
38|                        k, v = line.split("=", 1)
39|                        _os.environ.setdefault(k.strip(), v.strip())
40|
41|    def _sign_params(self, params: Dict) -> Dict:
42|        """Add timestamp and signature to params"""
43|        params["timestamp"] = int(time.time() * 1000)
44|        query_string = urlencode(params)
45|        signature = hmac.new(
46|            self.api_secret,
47|            query_string.encode(),
48|            hashlib.sha256
49|        ).hexdigest()
50|        params["signature"] = signature
51|        return params
52|
53|    def _get(self, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
54|        url = f"{self.base_url}{endpoint}"
55|        params = params or {}
56|        if signed:
57|            params = self._sign_params(params)
58|        response = self.session.get(url, params=params, timeout=self._timeout)
59|        response.raise_for_status()
60|        return response.json()
61|
62|    def _post(self, endpoint: str, params: Dict, signed: bool = True) -> Dict:
63|        url = f"{self.base_url}{endpoint}"
64|        if signed:
65|            params = self._sign_params(params)
66|        response = self.session.post(url, data=params, timeout=self._timeout)
67|        response.raise_for_status()
68|        return response.json()
69|
70|    def _delete(self, endpoint: str, params: Dict, signed: bool = True) -> Dict:
71|        url = f"{self.base_url}{endpoint}"
72|        if signed:
73|            params = self._sign_params(params)
74|        response = self.session.delete(url, params=params, timeout=self._timeout)
75|        response.raise_for_status()
76|        return response.json()
77|
78|    def price(self, symbol: str) -> float:
79|        """Get current price for symbol"""
80|        data = self._get("/api/v3/ticker/price", {"symbol": symbol})
81|        return float(data["price"])
82|
83|    def balance(self, asset: str) -> float:
84|        """Get free balance for asset"""
85|        data = self._get("/api/v3/account", signed=True)
86|        for item in data["balances"]:
87|            if item["asset"] == asset:
88|                return float(item["free"])
89|        return 0.0
90|
91|    def order_book_imbalance(self, symbol: str, limit: int = 20) -> Tuple[float, float, float]:
92|        """
93|        Returns (bid_qty, ask_qty, imbalance_ratio)
94|        imbalance_ratio = bid_qty / ask_qty
95|        """
96|        params = {"symbol": symbol, "limit": limit}
97|        data = self._get("/api/v3/depth", params)
98|        
99|        bid_qty = sum(float(b[1]) for b in data["bids"])
100|        ask_qty = sum(float(a[1]) for a in data["asks"])
101|        
102|        imbalance = bid_qty / ask_qty if ask_qty > 0 else float('inf')
103|        return bid_qty, ask_qty, imbalance
104|
105|    def market_buy(self, symbol: str, quantity: float) -> Dict:
106|        """Place market buy order"""
107|        params = {
108|            "symbol": symbol,
109|            "side": "BUY",
110|            "type": "MARKET",
111|            "quantity": f"{quantity:.6f}"
112|        }
113|        return self._post("/api/v3/order", params)
114|
115|    def market_sell(self, symbol: str, quantity: float) -> Dict:
116|        """Place market sell order"""
117|        params = {
118|            "symbol": symbol,
119|            "side": "SELL",
120|            "type": "MARKET",
121|            "quantity": f"{quantity:.6f}"
122|        }
123|        return self._post("/api/v3/order", params)
124|
125|    def limit_sell(self, symbol: str, quantity: float, price: float) -> Dict:
126|        """Place limit sell order"""
127|        params = {
128|            "symbol": symbol,
129|            "side": "SELL",
130|            "type": "LIMIT",
131|            "timeInForce": "GTC",
132|            "quantity": f"{quantity:.6f}",
133|            "price": f"{price:.6f}"
134|        }
135|        return self._post("/api/v3/order", params)
136|
137|    def get_open_orders(self, symbol: str) -> list:
138|        """Get open orders for symbol"""
139|        return self._get("/api/v3/openOrders", {"symbol": symbol}, signed=True)
140|
141|    def cancel_order(self, symbol: str, order_id: int) -> Dict:
142|        """Cancel order by ID"""
143|        params = {"symbol": symbol, "orderId": order_id}
144|        return self._delete("/api/v3/order", params)
145|
146|    # --- Adapter methods for WAR strategies ---
147|    def imbalance(self, symbol: str) -> float:
148|        _, _, imb = self.order_book_imbalance(symbol, 20)
149|        return imb
150|
151|    def open_orders(self, symbol: str) -> list:
152|        return self.get_open_orders(symbol)
153|
154|    def cancel_all(self, symbol: str):
155|        for o in self.open_orders(symbol):
156|            self.cancel_order(symbol, o["orderId"])
157|
158|    def ohlcv(self, symbol: str, interval: str = "5m", limit: int = 30) -> list:
159|        data = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
160|        return data
161|
162|    def atr(self, symbol: str, period: int = 14) -> float:
163|        klines = self.ohlcv(symbol, "5m", limit=period + 1)
164|        if not klines: return 0.0
165|        trs = []
166|        for i in range(1, len(klines)):
167|            h, l = float(klines[i][2]), float(klines[i][3])
168|            pc = float(klines[i-1][4])
169|            trs.append(max(h-l, abs(h-pc), abs(l-pc)))
170|        return sum(trs) / len(trs) if trs else 0.0
171|
172|    def balance_usdc(self) -> float:
173|        return self.balance("USDC")
174|
175|    def balance_sol(self) -> float:
176|        return self.balance("SOL")
177|
178|    def market_buy_quote(self, symbol: str, quote_amount: float) -> dict:
179|        """Buy using quote amount (USDC) instead of base quantity."""
180|        p = self.price(symbol)
181|        qty = round(quote_amount / p, 4) if p else 0
182|        return self.market_buy(symbol, qty)
183|
184|
185|if __name__ == "__main__":
186|    engine = BinanceEngine()
187|    print("Price SOLUSDC:", engine.price("SOLUSDC"))
188|    print("USDC Balance:", engine.balance("USDC"))
189|    bid, ask, imb = engine.order_book_imbalance("SOLUSDC", 20)
190|    print(f"Order book - Bid: {bid:.2f}, Ask: {ask:.2f}, Imbalance: {imb:.2f}")

============================================================
# FILE: v5_ws_engine.py
============================================================
1|"""WebSocket-powered engine — sub-millisecond price reads, zero API rate burn."""
2|import json
3|import time
4|import threading
5|from typing import Dict, Optional, Tuple
6|
7|try:
8|    import websocket
9|except ImportError:
10|    websocket = None
11|
12|from engine import BinanceEngine
13|
14|
15|class WSEngine(BinanceEngine):
16|    """BinanceEngine with WebSocket price + order-book cache.
17|
18|    Prices and order books update in real-time via a background thread.
19|    REST calls are used only for orders and balances (authenticated endpoints).
20|    """
21|
22|    def __init__(self, config_path: str = "config/war_config.json"):
23|        super().__init__(config_path)
24|
25|        # Real-time caches (updated by WS thread)
26|        self._prices: Dict[str, float] = {}         # symbol -> last price
27|        self._order_books: Dict[str, dict] = {}      # symbol -> {"bids": [...], "asks": [...]}
28|        self._ws_connected = False
29|        self._ws_thread: Optional[threading.Thread] = None
30|        self._ws_running = False
31|        self._ws_lock = threading.Lock()
32|
33|        # Symbols to track
34|        self._symbols = self.config.get("symbols", ["SOLUSDC"])
35|        self._streams_connected: Dict[str, bool] = {}
36|
37|        # Start WS in background if websocket library available
38|        if websocket:
39|            self._start_ws()
40|
41|    # ── WebSocket background thread ────────────────────────
42|    def _start_ws(self):
43|        """Launch WebSocket connection in a daemon thread."""
44|        self._ws_running = True
45|        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True)
46|        self._ws_thread.start()
47|
48|    def _ws_loop(self):
49|        """Connect to Binance combined streams and process messages."""
50|        # Combined stream: tickers (price) + depth@100ms (order book) for all symbols
51|        streams = []
52|        for sym in self._symbols:
53|            streams.append(f"{sym.lower()}@ticker")
54|            streams.append(f"{sym.lower()}@depth20@100ms")
55|
56|        stream_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
57|        base_url = self.config.get("exchanges", {}).get("binance", {}).get("ws_url",
58|                        "wss://stream.binance.com:9443/ws")
59|
60|        # Build URL using configured WS base
61|        if base_url.endswith("/ws"):
62|            stream_url = f"{base_url[:-3]}/stream?streams={'/'.join(streams)}"
63|
64|        while self._ws_running:
65|            try:
66|                ws = websocket.WebSocketApp(
67|                    stream_url,
68|                    on_message=self._on_ws_message,
69|                    on_error=self._on_ws_error,
70|                    on_close=self._on_ws_close,
71|                    on_open=self._on_ws_open,
72|                )
73|                # Run with ping interval to keep alive
74|                ws.run_forever(ping_interval=30, ping_timeout=10)
75|            except Exception as e:
76|                print(f"  ⚠️ WS connection error: {e} — retrying in 5s")
77|                time.sleep(5)
78|
79|    def _on_ws_open(self, ws):
80|        with self._ws_lock:
81|            self._ws_connected = True
82|        print(f"  🔗 WebSocket connected | {len(self._symbols)} symbols")
83|
84|    def _on_ws_close(self, ws, close_status_code, close_msg):
85|        with self._ws_lock:
86|            self._ws_connected = False
87|        print(f"  🔌 WebSocket disconnected ({close_status_code}) — reconnecting...")
88|
89|    def _on_ws_error(self, ws, error):
90|        print(f"  ⚠️ WS error: {str(error)[:100]}")
91|
92|    def _on_ws_message(self, ws, message):
93|        """Parse incoming WS message and update caches."""
94|        try:
95|            data = json.loads(message)
96|            stream = data.get("stream", "")
97|            event = data.get("data", {})
98|
99|            if "@ticker" in stream:
100|                sym = event.get("s", "")
101|                price = float(event.get("c", 0))
102|                if sym and price > 0:
103|                    with self._ws_lock:
104|                        self._prices[sym] = price
105|
106|            elif "@depth" in stream:
107|                sym = event.get("s", "")
108|                if sym:
109|                    with self._ws_lock:
110|                        self._order_books[sym] = {
111|                            "bids": event.get("bids", []),
112|                            "asks": event.get("asks", []),
113|                            "ts": time.time()
114|                        }
115|        except Exception:
116|            pass  # Ignore malformed messages
117|
118|    def stop(self):
119|        """Stop WebSocket thread."""
120|        self._ws_running = False
121|
122|    # ── Overridden methods (WS-first, REST fallback) ──────
123|    def price(self, symbol: str) -> float:
124|        """Get price from WS cache (instant) or REST fallback."""
125|        with self._ws_lock:
126|            p = self._prices.get(symbol, 0)
127|        if p > 0:
128|            return p
129|        # REST fallback
130|        return super().price(symbol)
131|
132|    def order_book_imbalance(self, symbol: str, limit: int = 20) -> Tuple[float, float, float]:
133|        """Get order book imbalance from WS cache (instant) or REST fallback."""
134|        with self._ws_lock:
135|            ob = self._order_books.get(symbol)
136|        if ob and ob.get("bids") and time.time() - ob.get("ts", 0) < 5:
137|            bids = ob["bids"][:limit]
138|            asks = ob["asks"][:limit]
139|            bid_qty = sum(float(b[1]) for b in bids)
140|            ask_qty = sum(float(a[1]) for a in asks)
141|            imbalance = bid_qty / ask_qty if ask_qty > 0 else float('inf')
142|            return bid_qty, ask_qty, imbalance
143|        # REST fallback
144|        return super().order_book_imbalance(symbol, limit)
145|
146|    # ── WS status ──────────────────────────────────────────
147|    @property
148|    def ws_alive(self) -> bool:
149|        with self._ws_lock:
150|            return self._ws_connected
151|
152|    @property
153|    def ws_prices(self) -> Dict[str, float]:
154|        with self._ws_lock:
155|            return dict(self._prices)
156|

============================================================
# FILE: v5_sync_strategies.py
============================================================
1|"""WAR Scalper — sync version for Denaro WAR main.py.
2|Uses BinanceEngine (REST) for rapid scalp entries on ATR spikes.
3|"""
4|import time
5|import math
6|from typing import Optional
7|
8|
9|class Scalper:
10|    """ATR-spike scalper. Monitors price drops from local high, enters on pullbacks."""
11|
12|    def __init__(self, engine, symbol: str, capital: float, config: dict):
13|        self.eng = engine
14|        self.symbol = symbol
15|        self.capital = capital
16|        self.cfg = config
17|        self.t = 0          # trade counter
18|        self.pnl = 0.0      # total P&L in USDC
19|        self._position = None
20|        self._entry_price = 0.0
21|        self._entry_qty = 0.0
22|        self._entry_time = 0.0
23|        self._high_30s = 0.0
24|        self._last_check = 0.0
25|        self._cooldown_until = 0.0
26|
27|        # Config
28|        self.entry_drop = self.cfg.get("entry_drop", 0.008)       # -0.8% from local high
29|        self.take_profit = self.cfg.get("take_profit", 0.004)     # +0.4%
30|        self.stop_loss = self.cfg.get("stop_loss", 0.02)          # -2%
31|        self.atr_spike_threshold = self.cfg.get("atr_spike_threshold", 3.0)
32|        self.cooldown_s = self.cfg.get("cooldown_after_exit_seconds", 30)
33|        self.max_hold_s = self.cfg.get("max_hold_seconds", 120)
34|
35|    def run(self) -> Optional[dict]:
36|        """Check market and return trade signal if triggered."""
37|        now = time.time()
38|
39|        # Manage open position
40|        if self._position is not None:
41|            return self._manage_position()
42|
43|        # Cooldown after last exit
44|        if now < self._cooldown_until:
45|            return None
46|
47|        # Get current price
48|        try:
49|            price = self.eng.price(self.symbol)
50|        except Exception:
51|            return None
52|
53|        if not price or price <= 0:
54|            return None
55|
56|        # Update 30s high
57|        if price > self._high_30s or self._high_30s == 0:
58|            self._high_30s = price
59|
60|        # Reset high periodically (every 60s)
61|        if now - self._last_check > 60:
62|            self._high_30s = price
63|            self._last_check = now
64|
65|        # Entry condition: price dropped entry_drop% below local high
66|        drop = (self._high_30s - price) / self._high_30s
67|        if drop >= self.entry_drop:
68|            # Calculate position size (use 50% of allocated capital)
69|            trade_capital = self.capital * 0.5
70|            qty = trade_capital / price
71|
72|            # Round quantity
73|            qty = self._round_qty(qty)
74|
75|            if qty > 0:
76|                self._entry_price = price
77|                self._entry_qty = qty
78|                # Place market buy via engine
79|                try:
80|                    result = self.eng.market_buy(self.symbol, qty)
81|                    if result and "orderId" in result:
82|                        self._position = "LONG"
83|                        self._entry_time = time.time()
84|                        self.t += 1
85|                        return {"action": "BUY", "price": price, "qty": qty}
86|                except Exception as e:
87|                    pass  # Order failed, will retry next cycle
88|
89|        return None
90|
91|    def _manage_position(self) -> Optional[dict]:
92|        """Check TP/SL for open position."""
93|        try:
94|            price = self.eng.price(self.symbol)
95|        except Exception:
96|            return None
97|
98|        if not price:
99|            return None
100|
101|        pnl_pct = (price - self._entry_price) / self._entry_price
102|
103|        # Take profit
104|        if pnl_pct >= self.take_profit:
105|            return self._close_position(price, "TP")
106|
107|        # Stop loss
108|        if pnl_pct <= -self.stop_loss:
109|            return self._close_position(price, "SL")
110|
111|        # Max hold time
112|        if self._entry_time > 0 and time.time() - self._entry_time > self.max_hold_s:
113|            return self._close_position(price, "TIMEOUT")
114|
115|        return None
116|
117|    def _close_position(self, price: float, reason: str) -> dict:
118|        """Market sell to close position."""
119|        try:
120|            result = self.eng.market_sell(self.symbol, self._entry_qty)
121|        except Exception:
122|            pass
123|
124|        pnl = (price - self._entry_price) * self._entry_qty
125|        self.pnl += pnl
126|        self._position = None
127|        self._cooldown_until = time.time() + self.cooldown_s
128|        self._high_30s = 0  # Reset high after trade
129|        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}
130|
131|    def _round_qty(self, qty: float) -> float:
132|        """Round quantity to reasonable decimal places."""
133|        if qty > 100:
134|            return math.floor(qty)
135|        elif qty > 1:
136|            return math.floor(qty * 100) / 100
137|        elif qty > 0.01:
138|            return math.floor(qty * 10000) / 10000
139|        else:
140|            return math.floor(qty * 1000000) / 1000000
141|
142|
143|class WhaleTracker:
144|    """Order-book imbalance whale detector."""
145|
146|    def __init__(self, engine, symbol: str, capital: float, config: dict):
147|        self.eng = engine
148|        self.symbol = symbol
149|        self.capital = capital
150|        self.cfg = config
151|        self.t = 0
152|        self.pnl = 0.0
153|        self._position = None
154|        self._entry_price = 0.0
155|        self._entry_qty = 0.0
156|        self._entry_time = 0.0
157|        self._cooldown_until = 0.0
158|
159|        self.imbalance_threshold = self.cfg.get("imbalance_threshold", 3.0)
160|        self.take_profit = self.cfg.get("take_profit_bps", 80) / 10000   # 80 bps = 0.8%
161|        self.stop_loss = self.cfg.get("stop_loss_bps", 150) / 10000      # 150 bps = 1.5%
162|        self.cooldown_s = self.cfg.get("cooldown_after_exit_seconds", 20)
163|        self.max_hold_s = self.cfg.get("max_hold_seconds", 180)
164|
165|    def run(self) -> Optional[dict]:
166|        now = time.time()
167|
168|        if self._position is not None:
169|            return self._manage_position()
170|
171|        if now < self._cooldown_until:
172|            return None
173|
174|        try:
175|            _, _, imbalance = self.eng.order_book_imbalance(self.symbol, 20)
176|        except Exception:
177|            return None
178|
179|        if imbalance >= self.imbalance_threshold:
180|            # Whale buying pressure detected
181|            try:
182|                price = self.eng.price(self.symbol)
183|            except Exception:
184|                return None
185|
186|            trade_capital = self.capital * 0.3
187|            qty = self._round_qty(trade_capital / price)
188|
189|            if qty > 0:
190|                try:
191|                    result = self.eng.market_buy(self.symbol, qty)
192|                    if result and "orderId" in result:
193|                        self._position = "LONG"
194|                        self._entry_price = price
195|                        self._entry_qty = qty
196|                        self._entry_time = now
197|                        self.t += 1
198|                        return {"action": "BUY", "price": price, "reason": f"imbalance={imbalance:.1f}"}
199|                except Exception:
200|                    pass
201|
202|        return None
203|
204|    def _manage_position(self) -> Optional[dict]:
205|        try:
206|            price = self.eng.price(self.symbol)
207|        except Exception:
208|            return None
209|        if not price:
210|            return None
211|
212|        pnl_pct = (price - self._entry_price) / self._entry_price
213|
214|        if pnl_pct >= self.take_profit:
215|            return self._close(price, "TP")
216|        if pnl_pct <= -self.stop_loss:
217|            return self._close(price, "SL")
218|        if self._entry_time > 0 and time.time() - self._entry_time > self.max_hold_s:
219|            return self._close(price, "TIMEOUT")
220|
221|        return None
222|
223|    def _close(self, price: float, reason: str) -> dict:
224|        try:
225|            self.eng.market_sell(self.symbol, self._entry_qty)
226|        except Exception:
227|            pass
228|        pnl = (price - self._entry_price) * self._entry_qty
229|        self.pnl += pnl
230|        self._position = None
231|        self._cooldown_until = time.time() + self.cooldown_s
232|        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}
233|
234|    def _round_qty(self, qty: float) -> float:
235|        if qty > 100:
236|            return math.floor(qty)
237|        elif qty > 1:
238|            return math.floor(qty * 100) / 100
239|        elif qty > 0.01:
240|            return math.floor(qty * 10000) / 10000
241|        else:
242|            return math.floor(qty * 1000000) / 1000000
243|
244|
245|class NewsReactor:
246|    """News sentiment reactor — stub that monitors price action."""
247|
248|    def __init__(self, engine, symbol: str, capital: float, config: dict):
249|        self.eng = engine
250|        self.symbol = symbol
251|        self.capital = capital
252|        self.cfg = config
253|        self.t = 0
254|        self.pnl = 0.0
255|        self._position = None
256|        self._entry_price = 0.0
257|        self._entry_qty = 0.0
258|        self._entry_time = 0.0
259|        self._cooldown_until = 0.0
260|        self._last_price = 0.0
261|        self._pump_counter = 0
262|
263|    def run(self) -> Optional[dict]:
264|        now = time.time()
265|
266|        if self._position is not None:
267|            return self._manage_position()
268|
269|        if now < self._cooldown_until:
270|            return None
271|
272|        try:
273|            price = self.eng.price(self.symbol)
274|        except Exception:
275|            return None
276|        if not price:
277|            return None
278|
279|        # Simplified "news" detection: rapid price increase >1% in one check
280|        if self._last_price > 0:
281|            change = (price - self._last_price) / self._last_price
282|            if change > 0.01:  # 1% pump
283|                self._pump_counter += 1
284|            else:
285|                self._pump_counter = 0
286|        self._last_price = price
287|
288|        # Enter on 2 consecutive pumps
289|        if self._pump_counter >= 2:
290|            trade_capital = self.capital * 0.25
291|            qty = self._round_qty(trade_capital / price)
292|            if qty > 0:
293|                try:
294|                    result = self.eng.market_buy(self.symbol, qty)
295|                    if result and "orderId" in result:
296|                        self._position = "LONG"
297|                        self._entry_price = price
298|                        self._entry_qty = qty
299|                        self._entry_time = now
300|                        self.t += 1
301|                        self._pump_counter = 0
302|                        return {"action": "BUY", "price": price, "reason": "momentum_pump"}
303|                except Exception:
304|                    pass
305|
306|        return None
307|
308|    def _manage_position(self) -> Optional[dict]:
309|        try:
310|            price = self.eng.price(self.symbol)
311|        except Exception:
312|            return None
313|        if not price:
314|            return None
315|
316|        pnl_pct = (price - self._entry_price) / self._entry_price
317|        # TP at 1.5%, SL at 2%
318|        if pnl_pct >= 0.015:
319|            return self._close(price, "TP")
320|        if pnl_pct <= -0.02:
321|            return self._close(price, "SL")
322|
323|        # Max hold 10min
324|        if self._entry_time > 0 and time.time() - self._entry_time > 600:
325|            return self._close(price, "TIMEOUT")
326|        return None
327|
328|    def _close(self, price: float, reason: str) -> dict:
329|        try:
330|            self.eng.market_sell(self.symbol, self._entry_qty)
331|        except Exception:
332|            pass
333|        pnl = (price - self._entry_price) * self._entry_qty
334|        self.pnl += pnl
335|        self._position = None
336|        self._cooldown_until = time.time() + 300  # 5 min cooldown
337|        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}
338|
339|    def _round_qty(self, qty: float) -> float:
340|        if qty > 100:
341|            return math.floor(qty)
342|        elif qty > 1:
343|            return math.floor(qty * 100) / 100
344|        elif qty > 0.01:
345|            return math.floor(qty * 10000) / 10000
346|        else:
347|            return math.floor(qty * 1000000) / 1000000
348|

============================================================
# FILE: v5_state_engine.py
============================================================
1|"""State Engine — Hedge fund method: classify market state, predict transitions."""
2|import time
3|from datetime import datetime, timedelta
4|
5|class StateEngine:
6|    """Hedge Fund State Classifier based on Lewis Jackson / Roan quant method.
7|    
8|    Concepts:
9|    1. States: BULL (>+5% in 20d), BEAR (<-5%), SIDEWAYS (between)
10|    2. Markov: future depends on current state, not past
11|    3. Transition Matrix: track all 9 state changes, predict probability
12|    4. Stickiness: current state most likely to continue
13|    """
14|    
15|    BULL = "BULL"
16|    BEAR = "BEAR"
17|    SIDEWAYS = "SIDEWAYS"
18|    
19|    def __init__(self, lookback_days: int = 20, threshold_pct: float = 5.0):
20|        self.lookback = lookback_days
21|        self.threshold = threshold_pct / 100  # 5% = 0.05
22|        self._history: list[str] = []  # daily states
23|        self._transitions: dict = {}   # "BULL->BULL": count
24|        self._current_state = self.SIDEWAYS
25|        self._last_price = 0.0
26|        self._price_20d_ago = 0.0
27|        self._last_day_check = ""
28|    
29|    def classify(self, current_price: float, ohlcv_20d: list) -> str:
30|        """Classify current market state based on 20-day price change.
31|        
32|        ohlcv_20d: list of [timestamp, open, high, low, close, volume] for ~20 days
33|        Returns: BULL, BEAR, or SIDEWAYS
34|        """
35|        if not ohlcv_20d or len(ohlcv_20d) < 5:
36|            return self.SIDEWAYS
37|        
38|        # Get price from 20 days ago vs now
39|        price_old = float(ohlcv_20d[0][4])  # close of first candle
40|        change = (current_price - price_old) / price_old
41|        
42|        if change > self.threshold:
43|            return self.BULL
44|        elif change < -self.threshold:
45|            return self.BEAR
46|        return self.SIDEWAYS
47|    
48|    def update(self, current_price: float, ohlcv_daily: list) -> dict:
49|        """Run daily update. Returns state info for strategy selection."""
50|        state = self.classify(current_price, ohlcv_daily)
51|        
52|        # Track transition
53|        if self._current_state and self._current_state != state:
54|            key = f"{self._current_state}->{state}"
55|            self._transitions[key] = self._transitions.get(key, 0) + 1
56|        
57|        old_state = self._current_state
58|        self._current_state = state
59|        
60|        # Calculate transition probabilities
61|        probs = self._transition_probabilities()
62|        
63|        return {
64|            "state": state,
65|            "previous": old_state,
66|            "changed": old_state != state,
67|            "stickiness": self._stickiness(),
68|            "next_state_prob": probs.get(state, {}),
69|            "transition_count": sum(self._transitions.values()),
70|        }
71|    
72|    def _transition_probabilities(self) -> dict:
73|        """Calculate probability of next state for each current state."""
74|        if not self._transitions:
75|            return {}
76|        probs = {}
77|        for state in [self.BULL, self.BEAR, self.SIDEWAYS]:
78|            total = sum(v for k, v in self._transitions.items() if k.startswith(state))
79|            if total > 0:
80|                probs[state] = {}
81|                for target in [self.BULL, self.BEAR, self.SIDEWAYS]:
82|                    key = f"{state}->{target}"
83|                    probs[state][target] = self._transitions.get(key, 0) / total
84|        return probs
85|    
86|    def _stickiness(self) -> float:
87|        """How likely is current state to continue? 0-1."""
88|        total = sum(self._transitions.values())
89|        if total == 0:
90|            return 0.5
91|        same = self._transitions.get(f"{self._current_state}->{self._current_state}", 0)
92|        return same / total if total > 0 else 0.5
93|    
94|    def strategy_signal(self) -> dict:
95|        """Return concrete trading signals based on state."""
96|        s = self._current_state
97|        if s == self.BULL:
98|            return {
99|                "primary": "momentum_long",
100|                "grid": False,
101|                "scalper": False