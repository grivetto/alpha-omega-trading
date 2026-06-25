# DENARO WAR Architecture

## Overview
DENARO WAR is a cryptocurrency trading system that captures volatility from three primary sources:
1. **News spikes** – especially Elon Musk tweets via the X (formerly Twitter) API or crypto‑news RSS feeds.
2. **Whale activity** – detected through order‑book depth anomalies.
3. **Market micro‑scalping** – driven by short‑term ATR spikes.

The system allocates a total capital pool across three strategies (70 % of the portfolio) as defined in `config/war_config.json`.

---

## 1. News Reactor (Elon Musk & Crypto‑News)
* **Data sources**: X API (search recent tweets for keywords like *Elon Musk*, *Tesla*, *Dogecoin*) and a generic crypto‑news RSS feed.
* **Signal detection**:
  * Count keyword occurrences in the last minute.
  * When the count exceeds a configurable threshold, raise a *high‑confidence* alert.
* **Trade logic**:
  * Allocate **10 %** of the *news* capital bucket.
  * Place a market‑buy order.
  * Exit via market‑sell when price is **+1.5 %** (take‑profit) or **‑2 %** (stop‑loss).

---

## 2. Whale Tracker
* **Data source**: Binance REST order‑book endpoint (`/api/v3/depth`).
* **Signal detection**:
  * Every 15 seconds fetch the top 20 bid/ask levels.
  * Compute **imbalance = total_bid_qty / total_ask_qty**.
  * An imbalance **> 3:1** indicates whale pressure on the bid side (or the inverse for asks).
* **Trade logic**:
  * Allocate **30 %** of the *whale* capital bucket.
  * Enter on the side of the imbalance (buy if bids dominate, sell short otherwise).
  * Exit at **+0.8 %** profit or **‑1.5 %** loss.

---

## 3. Scalper (ATR Spike)
* **Signal detection**:
  * Continuously track recent high (max price of the last 30 seconds).
  * When price drops **‑0.8 %** from that high, trigger a buy.
* **Trade logic**:
  * Uses the *scalper* capital bucket (40 % of allocated capital).
  * Sell at **+0.4 %** profit; stop‑loss at **‑2 %**.
  * Checks market every **5 seconds**; never exceeds the allocated bucket.

---

## 4. Capital Allocation
* Total capital is split according to `war_config.json`:
  * **Scalper** – 40 %
  * **Whale Tracker** – 30 %
  * **News Reactor** – 30 %
* Each strategy receives an independent *capital bucket* that it manages.
* Global risk limits defined in the config (max 5 % per trade, daily loss halt at 3 %).

---

## 5. Shared Engine (`engine.py`)
* Implements direct Binance REST calls using **HMAC‑SHA256** authentication (no ccxt).
* Provides helper methods:
  * `price(symbol)` – latest ticker price.
  * `balance(asset)` – account free balance.
  * `order_book_imbalance(symbol)` – returns bid/ask quantity ratio.
  * `market_buy(symbol, qty)`, `market_sell(symbol, qty)`, `limit_sell(symbol, qty, price)`.
* Handles request signing, timestamp, and basic error handling.

---

## 6. Orchestrator (`main.py`)
* Loads configuration.
* Starts each strategy in its own **thread** (or asyncio task) with its allocated capital.
* Every **5 minutes** logs aggregated statistics (PnL, capital usage, trade counts).
* Monitors daily loss limit and gracefully shuts down strategies when triggered.

---

*All code lives under `/c/dev/alpha-omega-trading/denaro_war/` and is ready for unit‑testing and live deployment.*