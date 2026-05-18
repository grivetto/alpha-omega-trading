# SOP-002: Dashboard Data Pipeline

## Scopo
Collezionare, aggiornare e servire i dati del sistema Denaro ogni minuto.

## Trigger
Cron job: `* * * * *` su mc2.

## Flusso

1. **Collect (mc2)**
   - `collect_dashboard_data.py`: 
     - Fetch balance da Binance API (HTTP direct, no ccxt)
     - Fetch prezzi EUR da ticker Binance
     - Parse legion_production.log per stato bot
     - Query trades.db per statistiche
     - Scrive `dashboard/public/mc2.json`

2. **Collect (nuvola via SSH)**
   - `collect_dashboard.py` → ssh sergio@nuvola → collect_dashboard_nuvola.py
   - Scp risultato su mc2

3. **Collect (MARCODG1 via SSH)**
   - Skip se chiavi placeholder (errore gestito silenziosamente)

4. **Sync (nuvola)**
   - `sync_dashboard.sh`: scp dei 3 JSON su nuvola
   - Destinazione: /var/www/html/denaro/

5. **Serve (nginx)**
   - https://sgrivett.ddns.net/denaro/ → index.html (SPA dashboard)
   - https://sgrivett.ddns.net/denaro/mc2.json → dati raw

## Error Recovery
- Collect fallisce → log su collector.log, JSON non viene aggiornato (dati precedenti restano)
- Sync fallisce → log su sync.log, dashboard mostra dati vecchi fino al prossimo sync
- SSH timeout 5s → non blocca il ciclo
