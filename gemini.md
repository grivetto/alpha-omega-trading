# Denaro – gemini.md
# Project Constitution — Schema dati, regole, invarianti

## TELEGRAM
BOT_TOKEN=8183973303:AAFwVUK0LUlyyTby_V0O3U_uMt4V7fXgW8I

## SCHEMA: trades (SQLite)
- id INTEGER PK
- bot_name TEXT
- symbol TEXT (es. "SOL/EUR")
- side TEXT ("BUY"|"SELL")
- entry_price REAL
- exit_price REAL
- quantity REAL
- entry_time DATETIME
- exit_time DATETIME
- gross_pnl REAL
- fees REAL
- net_pnl REAL
- exit_reason TEXT

## SCHEMA: bot_state (SQLite)
- bot_name TEXT PK
- is_in_position BOOLEAN
- entry_price REAL
- quantity REAL
- tp REAL (take profit)
- sl REAL (stop loss, -10% da entry)
- entry_time DATETIME
- last_heartbeat REAL (unix timestamp)
- exchange_name TEXT

## SCHEMA: capital_pool (SQLite)
- key TEXT PK ("eur_free", "total_eur", "max_trade")
- value REAL
- updated_at REAL

## SCHEMA: system_health (SQLite)
- id INTEGER PK
- ts DATETIME
- node TEXT ("mc2"|"nuvola"|"marcodg1")
- metric TEXT
- value REAL
- alert BOOLEAN

## BEHAVIOURAL RULES
1. HARD STOP: EUR libero < 5€ => nessun nuovo trade, log CRITICAL
2. DRAWDOWN: se drawdown > 10% => KILL SWITCH, stop TUTTI i bot, notify Telegram
3. OOM GUARD: se RAM > 80% o swap > 70% => stop bot non essenziali
4. POSITION LIMIT: max 15% del capitale totale per trade
5. STOP LOSS: fisso -10% da entry price (non negoziabile)
6. CIRCUIT BREAKER: 3 loss consecutivi => bot paused 1h, notify
7. HEARTBEAT: ogni bot deve heartbeat ogni 60s, se 120s missing => restart
8. SOLO IN SYSTEMD: nessun bot in screen/tmux, solo systemd user services
9. NO OVERLAP: due bot NON possono tradare la stessa coppia
10. LOG: ogni decisione va in log strutturato (json) su disco

## INVARIANTI
- gemini.md e' LEGGE: se cambia schema, prima questo file poi il codice
- tools/ = script Python deterministici, testabili
- architecture/ = SOP markdown
- .tmp/ = file effemeri
- WAL mode su SQLite sempre
- Tutto il deploy passa per git (repo alpha-omega-trading)
