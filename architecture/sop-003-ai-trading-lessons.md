# SOP-003: AI Trading Lessons — Alpha Arena Case Study

## Fonte
Video: [I gave 3 AIs $1,000 to trade for me](https://www.youtube.com/watch?v=857ejsBc3IA)
Architettura testata: Price tracker (2min) → DB → LLM decision (5min) → Backpack exchange
Risultato 24h: ~$500k volume, +$40-67 profit netto (flat), **tutto il profitto da un singolo trade**

## 🎯 Lezione 1: Single-Trade Dependency (la più importante)

> "All my profit came from a single $10k SOL long trade. Without that trade, the whole thing was break-even or negative."

**Implicazione per Denaro:** Se la strategia dipende da 1-2 colpi vincenti, non è trading — è gambling.

**Azioni:**
- Ogni bot deve generare almeno 3-5 segnali/giorno indipendentemente
- Se un bot fa 3 giorni con 0-1 trades, va messo in pausa e rivisto
- Distribuire il capitale su strumenti NON correlati (ETH, BTC, SOL già ok)
- Metriche da monitorare: trade_count/giorno, win_rate, avg_profit_per_trade

## 🏗 Lezione 2: Sub-Account Architecture (isolation pattern)

L'autore ha scoperto a proprie spese che usare lo stesso `account_index` per tutti i bot causava
errore "400 invalid signature" perché gli ordini collidevano.

**Pattern usato:** Ogni bot → proprio sub-account → propria API key dedicata.

**Applicazione a Denaro:**
- Abbiamo già 3 API key diverse (una per server), ma non per-bot su stesso server
- Se la Squadra cresce, ogni bot dovrebbe avere un sub-account Binance separato
- Vantaggio: isolation totale, se un bot crasha non blocca gli altri
- Svantaggio: gestione più complessa dei bilanci

**Stato attuale Denaro:** Uso di diverse API key per server è un buon compromesso
per la scala attuale. Se si aggiungono nuovi bot su mc2, creare sub-account.

## 📊 Lezione 3: Multi-Timeframe Context

L'autore passa ALL'LLM due blocchi di dati:
1. **Short-term:** 4 ore di candele 5min (~48 candele)
2. **Long-term:** 3 giorni di dati aggregati per trend generale

**Implementato in Denaro:** `utils/indicators.py` → `aggregate_timeframes()`
Restituisce RSI, MACD, SMA, EMA, VWAP, ATR% per ENTRAMBI i timeframe + divergence detection.

**Come usarlo in una strategia:**
```python
from utils.indicators import aggregate_timeframes

ohlcv_5m = await core.fetch_ohlcv("SOL/EUR", "5m", 48)   # 4 ore
ohlcv_1h = await core.fetch_ohlcv("SOL/EUR", "1h", 72)   # 3 giorni
ctx = aggregate_timeframes(ohlcv_5m, ohlcv_1h)

if ctx["divergence"] == "bullish":
    # Short ipervenduto + long trend up = BUY
elif ctx["divergence"] == "bearish":
    # Short ipercomprato + long trend down = SELL
```

## 📈 Lezione 4: MACD Come Indicatore Primario

MACD è stato l'indicatore più usato dall'LLM nel video. Aiuta a determinare:
- **Momentum:** Histogram positivo = bullish, negativo = bearish
- **Divergenze:** Prezzo fa nuovi massimi ma MACD no = inversione imminente
- **Crossover:** MACD line attraversa signal line = entry signal

**Implementato in Denaro:** `utils/indicators.py` → `calculate_macd(prices)`
Restituisce macd_line, signal_line, histogram, histogram_pct.

## 🛡 Lezione 5: Failsafe Gaps (cosa mancava)

L'autore ha ammesso: **non c'era un kill switch automatico.** Se andava in drawdown,
l'unica protezione era svegliarsi la mattina.

**Checklist failsafe per Denaro:**

| Failsafe | Stato Denaro | Note |
|----------|-------------|------|
| Max daily loss (-5%) | ✅ RiskManager.check_daily_loss() | Attivo |
| Max consecutive losses | ❌ Manca | Da aggiungere (es. 5 perdite consecutive = stop 24h) |
| Emergency close-all | ✅ Kill switch orchestrator | Presente |
| Max daily trade count | ❌ Manca | Da aggiungere (es. max 10 trades/bot/giorno) |
| Max drawdown per bot | ❌ Manca | Da aggiungere (es. -20% su capitale bot = disattiva) |
| Volatility-based sizing | ✅ RiskManager.calculate_size() | ATR-based |
| Position concentration | ❌ Manca | Max % capitale su singolo asset |

## 🔄 Lezione 6: Architettura a Due Tempi

Il video separa nettamente:
- **Data collection** (ogni 2 min) — fetch prezzi e salva in DB
- **Decision making** (ogni 5 min) — fetch dal DB, analizza, decide

**Vantaggio:** Il DB fa da buffer. Se LLM ci mette 30 secondi, non perdi dati.

**Applicazione Denaro:** L'orchestrator già fa tutto in un loop unico con refresh balance + OHLCV.
Pattern già ok per la scala attuale, ma se la latenza diventa critica si può separare
in due loop: collector (frequente) + trader (meno frequente).

## ⚠️ Riepilogo Rischi Identificati

1. **Single-trade dependency** — Diversificare o accettare che è speculazione
2. **No position concentration limit** — Aggiungere max % capitale per asset
3. **No consecutive loss protection** — Aggiungere stop-loss temporale (24h)
4. **Drawdown per-bot** — Aggiungere max drawdown individuale
5. **Volume come unico filtro** — Il video aveva solo position sizing basic

## Vedi anche
- `sop-001-trade-execution.md` — Flusso di esecuzione trades
- `utils/indicators.py` — MACD, multi-timeframe, VWAP
- `utils/risk_engine.py` — RiskManager per position sizing
