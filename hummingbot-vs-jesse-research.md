# Hummingbot vs Jesse — execution-safety research (as of 2026-09-23)

## A. Hummingbot 2.17.0 (released 2026-09-22) — [release notes](https://hummingbot.org/release-notes/)

**1 Short.** Yes via perpetual connectors (spot = long-only). Executors carry `TradeType` + `PositionAction`; `is_perpetual_connector()` = `"perpetual" in connector_name` ([executor_base.py](https://raw.githubusercontent.com/hummingbot/hummingbot/master/hummingbot/strategy_v2/executors/executor_base.py)). Docs: "On perpetual exchanges, they apply the take-profit and stop-loss levels … to manage a long or short position" ([positionexecutor](https://hummingbot.org/strategies/v2-strategies/executors/positionexecutor/)). 50+ connectors, "spot & perpetual futures"; headline perps Binance, Bybit, OKX, Gate.io, KuCoin, Hyperliquid, Lighter, Derive, dYdX ([exchanges](https://hummingbot.org/exchanges/)). Spot-margin short: **not verified**.

**2 Paper.** Exists, but as a *separate connector* `<ex>_paper_trade`, spot-only (default binance, kucoin, kraken, gate_io): "test Hummingbot and simulate trading strategies without risking any actual assets" ([paper-trade](https://hummingbot.org/client/global-configs/paper-trade/)). Docs claim **no** live-lifecycle fidelity, and a distinct connector is not the live code path. Perp paper trade: not documented.

**3 Look-ahead / walk-forward.** V2 backtest engine in core, driven by the Streamlit Dashboard ([backtest](https://hummingbot.org/dashboard/backtest/)); **no** walk-forward/OOS split documented. Dashboard is "no longer actively maintained by Hummingbot Foundation"; Condor recommended ([dashboard](https://hummingbot.org/dashboard/)).

**4 Maturity.** v2.17.0 (2026-09-22), ~monthly. API 2026-09-23: 20,178★, 4,957 forks, 171 open issues, `pushed_at` 2026-09-23T14:54:10Z, Apache-2.0, Hummingbot Foundation ([repo API](https://api.github.com/repos/hummingbot/hummingbot)). Contributor count: **not verified**.

**5 Daily trend.** Subclass `DirectionalTradingControllerBase` and/or a script; YAML config in `conf/controllers/`, run by `v2_with_controllers.py` ([config guide](https://hummingbot.org/blog/how-to-configure-a-v2-strategy-controller-in-hummingbot/)). Candles: `get_candles_df(connector, pair, interval, max_records)` ([data](https://hummingbot.org/strategies/v2-strategies/data/)); daily interval **not verified** (docs show '3m' only).

**6 Port.** Medium-hard: candle-loop/ccxt logic must become event-driven — connectors replace exchange calls, controllers emit `ExecutorAction`, positions configured via `PositionExecutorConfig` + `TripleBarrierConf(stop_loss, take_profit, time_limit, trailing_stop…)`.

**7 Safety (source-verified).**
a) **Yes, executor-local:** `amount_to_close = open_filled_amount − close_filled_amount`; the close order is placed with `amount=self.amount_to_close`; `open_filled_amount` = its own open order's `executed_amount_base` — not total balance ([position_executor.py](https://raw.githubusercontent.com/hummingbot/hummingbot/master/hummingbot/strategy_v2/executors/position_executor/position_executor.py)). It is *not* read from `fetch_positions`; source comments warn ONEWAY netting breaks reduce-only (issues #8269/#8283).
b) **Partly:** SL is bot-side (`net_pnl_pct <= -stop_loss` → market close), so no resting exchange stop (offline = unprotected). On rejection `process_order_failed_event` logs "Close order failed … Retrying n/max_retries", requeues, and the SHUTTING_DOWN loop retries every 5 s until `max_retries` (default 10) → `FAILED`; `control_close_order` re-fetches the order via `_handle_update_error_for_lost_order`.
c) **Yes:** `buy()/sell()` generate the id with `get_new_client_order_id(...)` and send it as `client_order_id`; `tracking_states` / `restore_tracking_states()` ("Restore in-flight orders from saved tracking states…"); held orders deduped by `client_order_id` ([exchange_py_base.py](https://raw.githubusercontent.com/hummingbot/hummingbot/master/hummingbot/connector/exchange_py_base.py)).
d) **Yes:** fills accumulate in `executed_amount_base`; `control_take_profit` renews the TP order when its size differs from the open fill — "can happen with partial fills".
e) **Yes:** per-instance SQLite ledger — `hummingbot/model/{order,trade_fill,executors,position,funding_payment,inventory_cost,sql_connection_manager}.py`; per-strategy attribution via `controller_id`.

## B. Jesse 3.2.2 (23 Sep 2026) — [changelog](https://docs.jesse.trade/docs/changelog), [PyPI](https://pypi.org/project/jesse/)

**1 Short.** Futures: `should_short()`/`go_short()`; "First-class support for leveraged trading and short-selling"; spot: "Short selling is not supported in spot trading" ([futures-vs-spot](https://docs.jesse.trade/docs/strategies/futures-vs-spot)). Live venues: Binance Perp/Spot, Bybit USDT+USDC Perp/Spot, KuCoin USDT Perp/Spot, Kraken Pro Futures/Spot, Gate.io Perp/Spot, Hyperliquid, Lighter, Apex Omni; Alpaca "coming soon" ([supported-exchanges](https://docs.jesse.trade/docs/supported-exchanges/)). No spot-margin short.

**2 Paper.** Yes: "enable paper trading by turning on the 'Paper Trade' option on the 'Live' page" ([livetrade](https://docs.jesse.trade/docs/livetrade)). No fidelity claim; paper-only bugs are fixed separately (3.0.0: "Paper trading limit and stop orders now execute correctly after a temporary market-data connection gap") ⇒ distinct simulator. Faithfulness: **not verified**.

**3 Look-ahead / walk-forward.** Strongest. Multi-timeframe bias "**is completely taken care of** in Jesse" ([routes](https://docs.jesse.trade/docs/routes)); PyPI: backtests "without look-ahead bias". `optimize()` splits `training_candles`/`testing_candles` — testing is "completely held out and is never seen during the parameter search" (Optuna + Ray) ([optimize](https://docs.jesse.trade/docs/research/optimize)); documented 3-period 60-70/15-20/15-20 validation ([overfitting](https://docs.jesse.trade/docs/optimize/overfitting)); plus Monte Carlo and Rule Significance Testing (3.0.2 fixed same-bar bias).

**4 Maturity.** 3.2.2; last commit `b6d89c2` "release Jesse 3.2.2", 2026-09-23T12:24:54Z; 8,577★, 1,245 forks, 16 open issues, MIT, org jesse-ai ([repo API](https://api.github.com/repos/jesse-ai/jesse)). Effectively single-maintainer (Saleh Mir). **Live engine absent from the OSS repo** — a prebuilt, license-gated plugin (`jesse install-live`, `LICENSE_API_TOKEN`).

**5 Daily trend.** Python `Strategy` in `strategies/<Name>/__init__.py`; routes support **1D** ("custom timeframes are not supported yet"). Channel/EMA/ATR via `ta`; ATR trailing stop in `update_position()` using `qty = self.position.qty`; 2% risk via `utils.risk_to_qty(capital, risk_per_capital, entry_price, stop_loss_price, precision, fee_rate)` ([utils](https://docs.jesse.trade/docs/utils)). Examples: example-strategies page; MCP ships 10 complete strategies (2.2.3).

**6 Port.** Rewrite into the synchronous candle API: `before/after`, `should_long/short`, `go_long/short`, `self.buy/sell/stop_loss/take_profit`, `self.position`, `update_position()`, `get_candles()`, `hyperparameters()/self.hp`; no ccxt/asyncio. Realistically ~1–2 days per strategy.

**7 Safety.**
a) **Documented, not enforced:** spot mode forces exit targets into `on_open_position()` "because we can't be sure about our position size (`qty`) until it's actually open" ([futures-vs-spot](https://docs.jesse.trade/docs/strategies/futures-vs-spot)).
b) **Exchange-side stops possible** (unlike Hummingbot): "In futures mode, you can set `self.take_profit` and `self.stop_loss` in `go_long()`". Retry policy: **not verifiable** (closed source). Reconciliation evidenced: 2.1.3 "reconciling active stop orders after a restart"; 3.1.4 reconciliation "preventing failed history reconciliation from leaving partial database updates"; 3.1.5 "pending local restoration work".
c) **Idempotency: not verified** — no `clientOrderId` documentation, live code closed → flag.
d) **Yes:** "Partial Fills: supports entering and exiting positions in multiple orders"; fixes for over-counted qty across partial fills (2.1.0) and oversized `reduce_only` exits after a partial TP (2.2.1).
e) Peewee + Postgres persistence with per-session records (`peewee`, `psycopg2-binary` deps); the OSS repo exposes no live order/position ledger (plugin-side).

**Verified:** A1–A7 (A7b only partly), B1–B7 except B7c. **Unverified:** Hummingbot spot-margin short / 1d interval / perp paper / contributors; Jesse idempotency, SL retry, contributor count, paper-vs-live code-path identity.

**Verdict.** Hummingbot fixes a–e in open source at executor level; its weak points are a bot-side (non-resting) stop-loss and a paper mode that is a separate spot-only connector. Jesse fixes a/d/e and partly b (real exchange-side stops + documented restart reconciliation) but hides idempotency and retry policy inside a closed-source paid live plugin; its research pipeline (held-out optimization, 3-period validation, Monte Carlo, significance tests, 1D routes, explicit look-ahead handling) is decisively stronger.
