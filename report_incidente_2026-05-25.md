# REPORT INCIDENTE — Analisi Completa del Sistema Denaro
**Data:** 25 Maggio 2026  
**Analista:** Hermes AI  
**Oggetto:** Disastro multi-bot con perdita ~88% del capitale

---

## 1. RIEPILOGO ESECUTIVO

| Metrica | Valore |
|---------|--------|
| **Capitale iniziale stimato** | ~500+ € |
| **Capitale attuale** | ~60 € (di cui 30.49€ EUR liberi su Binance) |
| **Perdita totale** | ~440 € (~88%) |
| **Bot attivi ancora potenzialmente dannosi** | 3 (mc2_bot.py × 2, grid_bot_v3 su MARCODG1) |
| **Sistemi rotti/bloccati** | 3 (kill-switch squadra, dashboard, Telegram) |
| **Trade registrati** | 416 (PnL storico +118.69€ — non riflette le perdite reali) |

---

## 2. TIMELINE DEL DISASTRO

### Fase 1: Accumulo graduale (Maggio 10-19)
```
10 Mag:  Inizio trading orion (BTC/BNB EUR). PnL -8.27€
15 Mag:  orion fa +26.11€ — picco di fiducia
17 Mag:  marco_sol parte su SOL/EUR, +16.53€ subito
18 Mag:  marco_sol +20.91€ — sembra funzionare
19 Mag:  CAPITALE AL PICCO: ~228-229€ (portfolio tracker)
         Squadra: EUR=124.78 + Crypto=103.36 = 228.14€
```

### Fase 2: Deterioramento lento (Maggio 20-23)
```
20 Mag:  marco_sol -12.45€, portfolio inizia a scendere
21 Mag:  orion fa +105.73€ (colpo di fortuna?)
         MA portfolio totale rimane piatto a ~226-228€
         → le vincite vengono mangiate da perdite altrove
22 Mag:  portfolio scende a ~218-227€
23 Mag:  portfolio scende a ~214-224€ — trend bearish evidente
         serata: portfolio ~220€, ancora "gestibile"
```

### Fase 3: IL CRASH (24 Maggio 03:00 UTC)
```
02:00-03:00:  portfolio ancora ~220€, squadra active
03:00:31 →   portfolio = 41.38€ (da ~220€)  ← -180€ IN UN COLPO SOLO
03:00-03:03:  stabile a ~41.37€, probabilmente grid/stop market eseguiti
03:03:53 →   portfolio = 19.17€  ← -22€ addizionale (altra posizione killata)
03:04-03:17:  stabile a ~19.15€ (totale: -201€ dal picco)
03:17:55 →   portfolio = 60.0€ (probabile vendita forzata crypto residue)
03:18-04:03:  stabile a 60.0€ con squadra active
04:05:44 →   alpha-engine restart (systemd daily), squadra diventa inactive
             portfolio resta a 60.0€
04:43:       ultimo snapshot: 60.0€, tutti i bot inactive
```

### Fase 4: Stallo (24-25 Maggio)
```
Dopo il crash: nessun recupero, kill-switch bloccato
Squadra log: drawdown 73.6%, kill-switch ON da 23+ ore
Nuvola: bot riavviato (25 Mag 14:07) in regime choppy, 0 trade
MARCODG1: kill-loop portfolio 29.70€ < floor 35€
```

---

## 3. CAUSE DIRETTE DEL CRASH

### 3.1 SINGOLA STRATEGIA NON PROFITTEEVOLE SU SOL/EUR (marco_sol)
marco_sol ha fatto +15.15€ in 143 trade su ~10 giorni, ma la daily breakdown mostra una chiara degenerazione:
```
17 Mag: +16.53€  ← profittevole
18 Mag: +20.91€  ← picco
19 Mag:  -5.09€  ← inversione
20 Mag: -12.45€  ← perdita
21 Mag:  -8.35€  ← continua
22 Mag:  -3.29€  ← ancora negativo
23 Mag:  +6.88€  ← falso recupero
```
**Causa:** Grid/ scalping su SOL/EUR che ha funzionato 2 giorni, poi ha perso per 4 giorni consecutivi. Le perdite sono state coperte da orion che faceva +105€, mascherando il problema fino al crash.

### 3.2 NESSUN LIMITE DI PERDITA PER SINGOLO BOT
Il config squadra.json dice `drawdown_limit_pct: 5.0`, ma questo calcola il drawdown sul portfolio TOTALE. Nessun bot aveva uno stop-loss individuale. Quando SOL/EUR è crollato, il bot ha continuato a comprare (grid averaging) senza limite, bruciando tutto il capitale allocato.

### 3.3 KILL SWITCH INEFFICACE
Il kill-switch:
- Si attiva con drawdown >5% OPPURE portfolio < floor
- Quando si attiva, **cancella solo ordini aperti** — NON vende le posizioni aperte
- Non c'è meccanismo di recovery: resta bloccato per sempre
- Non invia notifiche utili (Telegram 401 da gg)

### 3.4 TUTTI I BOT TRADANO DALLO STESSO ACCOUNT
Tutte le istanze (mc2_bot.py, nuvola_bot.py, grid_bot_v3, orion, marco_sol) usano la **stessa API key Binance**. Non c'è separazione del capitale. Un bot in perdita può mangiarsi il capitale degli altri.

### 3.5 NESSUNA REGISTRAZIONE DELLE PERDITE REALI
Il DB trades mostra PnL +118.69€, ma il capitale reale è andato da 228€ → 60€ (-168€). 
**I trade che hanno causato la perdita NON sono registrati.** Probabilmente perché:
- Le vendite forzate del kill-switch non sono tracciate
- I grid bot non registrano le perdite parziali
- I trade aperti al momento del crash non sono mai stati chiusi "ufficialmente"

### 3.6 SYSTEMA MULTI-ISTANZA NON COORDINATO
- mc2_bot.py gira in **2 istanze** (PID 308638 e 385152) = double trading possibile
- Ogni server ha la propria copia del codice, spesso con versioni diverse
- Git mostra **72+ file untracked** su ogni server
- La dashboard è rotta da giorni (cerca orchestrator.py che non esiste)
- Telegram keys scadute su tutti i bot

---

## 4. STATO ATTUALE DEI SISTEMI

| Sistema | Stato | Dettaglio |
|---------|-------|-----------|
| **mc2_bot.py** | ⚠️ ATTIVO × 2 | PID 308638 + 385152. Possibile conflitto. |
| **alpha-engine** | ✅ Running | Daily restart 04:05, ma non fa trading |
| **squadra** | 🛑 KILL-SWITCH ON | Drawdown 73.6%, bloccato da 23+ ore |
| **nuvola_bot** | ✅ Attivo | PID 358387, regime choppy, 0 trade |
| **grid_bot_v3 (MARCODG1)** | ⚠️ Kill-loop | Portfolio 29.70€ < floor 35€, ciclo continuo |
| **denaro-dashboard** | 🛑 BROKEN | Manca orchestrator.py, 5363+ restart |
| **Telegram** | 🛑 SCADUTO | 401 Unauthorized su tutti i bot |
| **Git (tutti)** | 🟡 72+ untracked | Versioni diverse su ogni server |
| **Saldo Binance** | EUR 30.49 | + crypto dust (~10€ BTC, ~10€ ETH, ~10€ BNB) |

---

## 5. ANALISI PER BOT

### orion (BTC/BNB EUR)
- 231 trade, PnL +103.76€ (miglior bot)
- Un singolo giorno (21 Mag) ha fatto +105.73€
- Ha perso in 4 degli 8 giorni di attività
- **Verdetto:** Bot più profittevole, ma con alta varianza. Il +105€ è stato un outlier.

### marco_sol (SOL/EUR)
- 143 trade, PnL +15.15€
- Profittevole 2 giorni, in perdita 4
- **Verdetto:** Il bot che ha causato il crash. SOL/EUR ha avuto un movimento sfavorevole e il grid averaging ha amplificato le perdite.

### Legion (multi-simbolo su Nuvola + MARCODG1)
- 13 trade totali, PnL -0.62€
- Tutti chiusi con stop_loss o trailing_stop
- **Verdetto:** Inefficace ma non pericoloso. Perde sistematicamente.

### stellatron (ADA/EUR grid su Nuvola)
- 29 trade, PnL +0.40€
- Grid trading minimo su ADA
- **Verdetto:** Marginale, non contribuisce.

---

## 6. RACCOMANDAZIONI IMMEDIATE

### 🚨 URGENTE (fare SUBITO)
1. **FERMARE mc2_bot.py** — entrambe le istanze (sono potenzialmente dannose)
2. **FERMARE grid_bot_v3 su MARCODG1** — kill-loop sta bruciando commissioni
3. **RIAVVIARE Telegram** con API key funzionante
4. **AGGIORNARE .env** su tutti i server con Telegram key valida

### 🔧 PRIORITÀ ALTA (oggi/domani)
5. **Separare le API key Binance** — un bot = un set di chiavi con limiti di trading
6. **Convertire nuvola_bot e grid_bot a systemd** (come da tua preferenza)
7. **Aggiungere stop-loss INDIVIDUALE per bot** in config, non solo drawdown globale
8. **Fixare denaro-dashboard** — creare orchestrator.py stub o correggere il service

### 📋 PRIORITÀ MEDIA (questa settimana)
9. **Consolidare i DB trade** — un unico DB centralizzato per tutti i bot
10. **Ripulire il repository git** — commitare o rimuovere i 72+ file untracked
11. **Aggiungere daily report automatico via Telegram**
12. **Configurare alert su drawdown per singolo bot**

### ⚙️ SISTEMICI (architettura)
13. **Backtesting obbligatorio** — nessuna strategia va in produzione senza backtest
14. **Paper trading** — ogni nuovo bot deve fare 1 settimana su testnet
15. **Capitale allocato per bot** — budget fissi, non fondo comune
16. **PnL tracking obbligatorio** — ogni trade deve essere registrato, anche le emergency close

---

## 7. DATI GREZZI

### Capital Snapshots — giornaliero
```
Data        Snapshots   Min €     Media €    Max €
2026-05-19  1,168       227.22    228.25     229.30
2026-05-20  1,408       226.91    227.49     227.96
2026-05-21  1,402       225.84    227.24     228.60
2026-05-22  1,409       218.18    224.60     227.74
2026-05-23  1,382       213.76    217.73     223.75
2026-05-24    560        19.15    105.07     222.14
```

### Momento del Crash (24 Mag 03:00-03:18 UTC)
```
03:00:31   41.38€    ← PRIMO CROLLO da ~220€
03:00:43   41.38€
03:01:07   41.38€
03:01:31   41.39€
03:02:30   41.37€
03:03:05   41.37€
03:03:41   41.37€
03:03:53   19.17€    ← SECONDO CROLLO
03:04:53   19.17€
03:05:40   19.17€
...        ...       (stabile per ~14 minuti)
03:17:55   60.00€    ← RECUPERO PARZIALE (vendita crypto)
03:18-04:00 60.00€   ← stabile
04:05-04:43 60.00€   ← bot diventano inactive, ultimo snapshot
```

---

## 8. VERIFICA KILL SWITCH — PERCHÉ NON HA FUNZIONATO

Il kill-switch di squadra (drawdown limit 5%) si è attivato correttamente quando il drawdown ha superato il 5%. 

**Problemi:**
1. Il drawdown è calcolato sul portfolio TOTALE, non per singolo bot
2. Quando si attiva, **cancella ordini aperti** ma **non vende le posizioni aperte**
3. Senza vendita delle posizioni, il capitale resta "congelato" in asset deprezzati
4. Il kill-switch non ha un timer di recovery — rimane ON per sempre
5. Non c'è una strategia di uscita graduale (DCA out, partial close, etc.)

**Risultato:** Il kill-switch ha fermato il trading ma non ha protetto il capitale. Le posizioni aperte sono state liquidate dal mercato (movimento avverso) invece di essere chiuse strategicamente.

---

## 9. DOMANDE APERTE

1. **Quanto era il capitale iniziale REALE?** Le env dicono 500€ ma squadra.json dice 80€. Con tutti i depositi e prelievi, il numero esatto non è chiaro.
2. **Le perdite sono state solo sul bot o anche su operazioni manuali?** Non ci sono log di trade manuali.
3. **Perché le snapshot si fermano al 24 Mag 04:43?** Il collector si è fermato o il DB è stato disconnesso.
4. **marco_sol ha fatto +15€ di PnL ma ha contribuito alla perdita di 200€** — come è possibile? Probabilmente perché le posizioni aperte al momento del crash (con perdita non realizzata) non sono mai state registrate come trade chiusi. Il PnL nel DB riflette solo i trade COMPLETATI, non le posizioni aperte che sono state liquidate.

---

## CONCLUSIONE

Il sistema Denaro ha perso ~88% del capitale in 15 giorni di trading. Il profitto storico di +118.69€ dai trade registrati è ingannevole perché:
1. Le perdite reali non sono registrate (trade aperti → crash → perdita non tracciata)
2. Un singolo outlier (+105.73€ il 21 Mag da orion) ha mascherato la degenerazione
3. Il kill-switch ferma il trading ma non protegge il capitale (non vende posizioni)
4. L'architettura multi-server con API key condivisa è intrinsecamente fragile

**Lezione principale:** Un sistema di trading automated non è "profittevole" finché non dimostra di poter perdere controllatamente. Senza stop-loss individuali per bot, tracking obbligatorio di TUTTI i trade (incluse emergency close), e backtesting, qualsiasi strategia è un gioco d'azzardo con leva algoritmica.
