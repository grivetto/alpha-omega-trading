# TradingAgents — layer di ricerca advisory (2026-09-25)

Stato: INSTALLATO e VERIFICATO su mc2. Modalità **log-only**: nessun ordine,
nessuna chiave exchange, nessuna influenza sui bot live. È un layer di ricerca
per valutare se aggiunge valore ai segnali del progetto Denaro.

## Cos'è
Pipeline multi-agente LLM (TauricResearch/TradingAgents, MIT, submodule in
`tradingagents/`): analisti (market / news / social) → dibattito ricercatori
(bull vs bear + manager) → trader → risk team (3 profili) → Portfolio Manager.
Output: rating a 5 livelli — Buy / Overweight / Hold / Underweight / Sell —
con tesi dettagliata.

## Dove
- Submodule git: `tradingagents/` (upstream v0.5.1, commit `35543d0`).
- Venv isolato: `tradingagents/.venv` (editable install: `pip install -e .`).
- Config: `config/.env_tradingagents` (chmod 600, gitignored) — chiavi LLM
  (DeepSeek primaria; TypeSafe/JEV disponibile per lo screening social),
  `LANGCHAIN_TRACING_V2=false`.
- Symlink `tradingagents/.env → ../config/.env_tradingagents` (per uso da CLI).

## Modelli (quali e perché)
- provider `deepseek`: quick_think = deep_think = **`deepseek-v4-flash`**
  (escalation a `deepseek-v4-pro` possibile via env, costo ~3x).
- ⚠️ CAVEAT: usare l'ID `deepseek-v4-flash`, **NON** `deepseek-flash`.
  La capability table di v0.5.1 riconosce solo `deepseek-v4-flash`/`-pro`
  (pattern `^deepseek-v\d`): con `deepseek-flash` il framework NON sopprime
  `tool_choice`, DeepSeek (thinking mode) la rifiuta → tutti gli agent a
  structured output degradano a free-text. Con l'ID corretto: verificato OK.
- `output_language=Italian` (il rating 5-livelli resta a vocabolario EN ed è
  renderizzato correttamente; il parser non si rompe).
- max_debate_rounds=1, max_risk_discuss_rounds=1 (costo contenuto).

## Runner
`tools/tradingagents_advisory.py` — va lanciato col venv del submodule:

    tradingagents/.venv/bin/python tools/tradingagents_advisory.py --check
    tradingagents/.venv/bin/python tools/tradingagents_advisory.py --tickers BTC-USD,ETH-USD

- `--check`: preflight senza chiamate LLM (config risolta + chiave presente).
- Ticker in formato yfinance (`BTC-USD`); le coppie Denaro `BASE/EUR` sono
  normalizzate al mercato di riferimento `BASE-USD`.
- Output: `logs/tradingagents/advisory/<data>_<TICKER>.json` (completo),
  `logs/tradingagents/advisory.jsonl` (riepilogo), memory condiviso
  `logs/tradingagents/memory/trading_memory.md`, full-state in `runs/`.
- Lock anti-overlap (`logs/.../advisory/.lock`); exit 1 se un ticker
  fallisce (visibile in cron); un ticker rotto non blocca gli altri.

## Cron (mc2, utente sergio)
    10 6 * * *  <venv>/python tools/tradingagents_advisory.py --tickers BTC-USD,ETH-USD >> logs/tradingagents/cron.log 2>&1

06:10 CEST = fuori dalle peak-hours DeepSeek (9-12 / 14-18 Beijing); analisi
as-of oggi, coerente con l'uso live del framework.

## Costi misurati (run reali del 24-25/09)
- Per run: ~174k token input / 60-69k output; ~5.3 min; **~$0.04** (Flash).
- Cron BTC+ETH: ~$0.08/giorno ≈ **~$2.5/mese**. Cache-hit DeepSeek applicato
  automaticamente (≈98% di sconto sugli input ripetuti).
- Riferimento listino: v4-flash $0.14/M in, $0.28/M out; v4-pro $0.435/$0.87.

## Verifiche fatte
- 2 run end-to-end reali (24/09): BTC-USD → **Underweight**, ETH-USD → **Hold**.
- Structured output attivo su Sentiment/RM/Trader; il PM raramente risponde in
  free-text e il framework fa retry (rating comunque parsato). Parser rating
  verificato.

## Limiti noti (degradi gestiti, non bloccanti)
- StockTwits 403 da IP datacenter → sentiment ridotto (framework degrada
  pulito); Reddit a volte silente; FRED non configurato → macro assente.
- I rating sono input di RICERCA: nessuna decisione operativa dei bot dipende
  da questo layer. Non usare i rating come trigger ordini.

## Replica su un altro nodo
    git submodule update --init tradingagents
    python3 -m venv tradingagents/.venv
    tradingagents/.venv/bin/pip install -e tradingagents
    # creare config/.env_tradingagents (DEEPSEEK_API_KEY [+ TYPESAFE_API_KEY]), chmod 600
