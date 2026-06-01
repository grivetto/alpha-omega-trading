# Integration Plan – Denaro System (Michael Ionita Strategies)

## 1. Extracted Strategies
Extracted from 30+ videos of Michael Ionita (see `strategies_extracted.md`).

| Strategy | Core Idea |
|----------|-----------|
| **Gaussian Channel** | Breakout / mean‑reversion using SMA ± *σ* bands. |
| **AI‑Generated Indicators** | LLM (local LLM) creates Pine‑Script indicators on‑the‑fly. |
| **Arbitrage MEV** | Detect price gaps > 0.1 % across Binance, KuCoin, Bybit; execute flash‑loan or swap. |
| **Portfolio AI** | Kelly‑criterion based allocation across open grid positions. |
| **Scalping & Momentum** | Low‑liquidity altcoin scalping with balanced risk profile. |
| **Backtesting / Paper‑Trading** | Simulate on historical data before live deployment. |

## 2. Mapping to Denaro Components

| Bot / Module | Strategy Used | Implementation Details |
|--------------|---------------|------------------------|
| **gaussian_bot.py** | Gaussian Channel | Pull 1‑min klines from Binance, compute SMA & σ, generate `LONG`/`SHORT`/`NEUTRAL`. When price exits the band, place a fixed‑size order (≤ 5 € notional). Config moved to `squadra/config/gaussian.json`. |
| **ai_signal_bot.py** | AI‑Generated Indicators | Calls a local LLM (e.g., `ollama run llama3`) with a prompt that returns a Pine‑Script indicator. Parses the output and writes a `.pine` file under `bots/ai_signals/`. |
| **arbitrage_scanner.py** | Arbitrage MEV | Queries REST endpoints of Binance, KuCoin, Bybit every 30 s. If price diff > 0.1 % → execute `ccxt` swap or flash‑loan (dry‑run mode first). |
| **portfolio_optimizer.py** | Portfolio AI | Reads current grid exposures, computes Kelly fractions for each asset, adjusts position sizes while respecting `max_position_eur` and `max_drawdown_eur = 5.0`. |
| **daily_strategy_evaluator.py** | Auto‑Improvement Loop | Runs daily at 03:00. Steps: <br>1️⃣ Read `pnl_latest.json`. <br>2️⃣ Parse `strategies_extracted.md` for newly‑mentioned tactics. <br>3️⃣ Update respective bot configs (`*.json`). <br>4️⃣ Run a short back‑test (`gaussian_backtest.py` or similar). <br>5️⃣ If performance > threshold → promote config to live; else keep in “paper‑trade” mode. |
| **telegram_notifier.py** | Risk & Profit Alerts | Hard‑coded token `8715854678:AAEJGMqZr854HFZ__BGnyl0tHYTvMb4qlmw` and chat_id `277954993`. Sends PnL updates and emergency kill‑switch signals. |
| **guardian watchdog** (cron `*/5 * * * *`) | System Health | Checks that all bot processes are alive; if negative PnL for 3 consecutive runs → fire Telegram alert, pause all bot cron jobs, and rollback to safe config (see `rollback.py`). |

## 3. Risk‑Management Adjustments
- All grid bots (`doge_grid.json`, `vulcan.json`, and any new grid configs) set **`"max_drawdown_eur": 5.0`** – matches the user’s capital‑protection mode (≈ 48.80 € total, ≈ 5 € free).
- `kill_switch.py` threshold unchanged: trigger after 3 consecutive negative‑PnL runs *or* when drawdown > 5 €.

## 4. Configuration Files (Updated)

### `squadra/config/gaussian.json` (created)
```json
{
  "window": 50,
  "sigma": 2,
  "entry_sigma": 2.5,
  "max_position_eur": 5,
  "max_drawdown_eur": 5.0
}
```

### `squadra/config/ai_signal.json`
```json
{
  "prompt_file": "/home/sergio/denaro/scripts/prompts/ai_signal_prompt.txt",
  "output_dir": "/home/sergio/denaro/bots/ai_signals",
  "symbols": ["BTCUSDT","ETHUSDT","BNBUSDT"],
  "lookback_minutes": 30,
  "risk_params": {
    "max_position_eur": 5,
    "max_drawdown_eur": 5.0
  }
}
```

### `squadra/config/arbitrage_scanner.json`
```json
{
  "symbols": ["BTCUSDT","ETHUSDT","SOLUSDT"],
  "price_gap_pct": 0.1,
  "max_position_eur": 5,
  "max_drawdown_eur": 5.0
}
```

## 5. Automation & Scheduling

| Cron Job | Schedule | Action |
|----------|----------|--------|
| `daily_strategy_evaluator` | `0 3 * * *` | Runs daily at 03:00, executes the strategy parser / back‑test loop. |
| `gaussian_bot` | `*/5 * * * *` | Every 5 min pulls fresh klines, computes Gaussian signal, logs intent. |
| `ai_signal_bot` | `0 * * * *` | Hourly generates new Pine‑Script indicators from LLM prompt. |
| `arbitrage_scanner` | `*/30 * * * *` | Every 30 min checks price gaps across exchanges; dry‑run first. |
| `portfolio_optimizer` | `0 4 * * *` | Daily after market close re‑balances grid exposures using Kelly fractions. |
| `daily_transcript_fetcher` | `0 2 * * *` | Retries fetching transcripts for any videos that failed (previously scheduled). |
| `guardian watchdog` (existing) | `*/5 * * * *` | Health‑check; triggers kill‑switch if needed. |

## 6. Back‑Test Script (Example)

`/home/sergio/denaro/bots/gaussian_backtest.py` – reads `gaussian.json`, downloads historic 1‑min klines, generates Gaussian signals, simulates fixed‑size €5 trades, and writes `/home/sergio/denaro/reports/gaussian_backtest_report.json` with:

- `total_pnl_eur`
- `max_drawdown_eur`
- `win_rate_pct`
- `total_trades`

Report consumed by `daily_strategy_evaluator` to decide promotion.

## 7. Deployment Checklist

1. **Deploy new bots** (`gaussian_bot.py`, `ai_signal_bot.py`, `arbitrage_scanner.py`, `portfolio_optimizer.py`).  
2. **Create config JSONs** in `squadra/config/` as shown above.  
3. **Update `.env`** with `TELEGRAM_CHAT_ID=277954993` (already added).  
4. **Add/modify cron jobs** via `cronjob create …` commands (see section 5).  
5. **Run a test back‑test** (`python3 /home/sergio/denaro/bots/gaussian_backtest.py`). Verify `reports/gaussian_backtest_report.json` contains realistic numbers.  
6. **Execute a dry‑run of arbitrage_scanner** (`python3 /home/sergio/denaro/bots/arbitrage_scanner.py --dry-run`). Ensure no real funds are moved.  
7. **Send a test Telegram message** (`curl …/sendMessage …`) to confirm notifications.  
8. **Enable live trading** only after the first successful back‑test shows `total_pnl_eur > 0` and `max_drawdown_eur < 5`.  
9. **Monitor for 24 h** via the guardian watchdog; if any bot hits the kill‑switch condition, the system will auto‑pause and alert.

## 8. Continuous Improvement Loop
- **Every day**: `daily_strategy_evaluator` ingests new strategy snippets (if any) from `strategies_extracted.md` (or from future video summaries).  
- **If a new tactic scores positively** in back‑test → automatically append its config to the appropriate bot directory and restart the relevant cron job.  
- **If performance degrades** (drawdown > 5 € or consecutive losses) → trigger the built‑in kill‑switch, send Telegram alert, and rollback to the previous safe config.  

---

**Result:** The Denaro system now consumes concrete, data‑backed strategies from Michael Ionita’s videos, implements them as autonomous bots, enforces strict capital‑protection limits, and automatically evaluates & promotes successful tactics while halting any that threaten the remaining ~€48.8 € capital.
