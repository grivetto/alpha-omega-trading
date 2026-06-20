# Denaro Trading Engine v2 — Multi-Agent LLM Architecture

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   AgentOrchestrator                       │
│  ┌──────────┐    ┌────────────┐    ┌──────────┐         │
│  │ Analyst  │───→│ Risk Mgr  │───→│ Executor │──→      │
│  │ Agent    │    │ (LLM veto)│    │ Agent    │  Trade   │
│  └──────────┘    └────────────┘    └──────────┘         │
│       ↑               ↑                  ↑               │
│  Market Data      LLM Inference     Exchange API         │
│  (ccxt WS)       (Ollama/LM Studio)  (ccxt REST)         │
└──────────────────────────────────────────────────────────┘
```

### Agents

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Analyst** | Analizza dati di mercato in real-time | Ticker, Order Book, OHLCV | `ContextState` (regime, anomalie, confidence) |
| **Risk Manager** | Valuta il rischio, ha **veto assoluto** | `ContextState` + LLM | `RiskAssessment` (GO/NO-GO/REDUCE/LIQUIDATE) |
| **Executor** | Calcola entrate/uscite dinamiche | `ContextState` + `RiskAssessment` | `ExecutionSignal` (prezzo, quantità, tipo) |

### Flusso di esecuzione (per ogni simbolo)

```
Analyst.analyse(symbol)          → ContextState
RiskManager.evaluate(context)    → RiskAssessment (con LLM)
Executor.compute_signal(ctx,risk)→ ExecutionSignal
Orchestrator.execute(signal)     → Trade / Paper log
         ↓ loop ogni N secondi
```

## Directory Structure

```
trading_engine_v2/
├── core/
│   ├── __init__.py
│   ├── orchestrator.py    # AgentOrchestrator — controller centrale
│   ├── config.py          # Configurazione (env vars)
│   ├── exceptions.py      # Gerarchia eccezioni personalizzate
│   └── logger.py          # Logger strutturato per agente
├── agents/
│   ├── __init__.py
│   ├── analyst.py         # Agente Analista del Contesto
│   ├── risk_manager.py    # Agente Gestore del Rischio (LLM)
│   └── executor.py        # Agente Esecutore
├── models/
│   ├── __init__.py        # Modelli dati (MarketSnapshot, ContextState, ecc.)
├── connectors/
│   ├── __init__.py
│   ├── exchange.py        # Connettore exchange (ccxt async)
│   └── llm_client.py      # Client LLM (Ollama/LM Studio)
├── services/
│   └── (future)
├── tests/
│   └── (future)
├── requirements.txt
└── README.md
```

## Configurazione

Copia `.env.example` in `.env` e imposta:

```env
# Exchange
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
EXCHANGE_ID=binance

# LLM (Ollama / LM Studio)
LLM_ENDPOINT=http://localhost:11434/v1
LLM_MODEL=llama3.2:3b
LLM_API_KEY=ollama
LLM_TIMEOUT=30

# Trading
TRADING_SYMBOLS=SOL/USDC,ADA/USDC
EXECUTION_MODE=paper
ANALYSIS_INTERVAL=15

# Risk
MAX_DAILY_LOSS_PCT=5.0
MAX_DRAWDOWN_PCT=10.0
MAX_POSITION_PCT=25.0
```

## Esecuzione

```bash
cd trading_engine_v2
pip install -r requirements.txt
python -m core.orchestrator
```

In **paper mode** (default) nessun ordine reale viene piazzato — tutto viene loggato.

## Requisiti

- Python 3.11+
- ccxt (async)
- httpx
- Ollama o LM Studio con modello LLM in esecuzione su `localhost:11434`
- API key Binance (spot)
