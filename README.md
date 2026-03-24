
# 🚀 ORBITAL COMMAND: NEON SQUAD
**Versione Attuale:** Alpha 0.99 (Pre-Beta)
*La release Beta 1.0 verrà rilasciata solo ed esclusivamente al raggiungimento e mantenimento stabile dell'obiettivo di 100€ di profitto netto giornaliero.*

## 👁️ CHARLIE INFRASTRUCTURE (Zabbix Monitor)
La nuova architettura si regge su un guardiano supremo: **CHARLIE** (o Zabbix Watchdog). Questo demone in background scruta la memoria RAM, l'uso CPU e il battito cardiaco (ultimo aggiornamento nei log) di ciascuno dei bot operativi. Qualora un bot, a causa di congestioni di rete o chiamate API lente si "incastri" in stato *Zombie*, CHARLIE procede con un `kill -9` istantaneo per liberare risorse, lasciando che il `lite_guardian` lo riporti in vita fresco. Questo garantisce uptime eterno senza mai sforare la soglia fatale di 4GB RAM (OOM).

## ⚔️ LA LEGIONE E L'EFFETTO SCIAME (40 BOTS ONLINE)
Invece di avere un singolo mega-algoritmo Pandas-TA (che divorava RAM ad ogni ricalcolo per 30 monete), la "Neon Squad" ha frazionato la mente operativa in micro-servizi Python isolati:
1. **L'Armata Speciale (12 Bot):** Ognuno specializzato in una singola inefficienza di mercato (es. `STABLE_SCALPER` su EUR/USDT spread, `FLASH_CATCHER` su ombre -4%, `RSI_HUNTER` per divergenze M5, `DARKPOOL` per arbitraggi triangolari).
2. **I Legionari (28 Bot):** Una rete a strascico (da `legion_01_ada.py` a `legion_28_ftm.py`) schierata simultaneamente. Usano chiamate HTTP REST debolissime (1 richiesta/minuto) e fanno pulizia spazzatura (`gc.collect()`) fissa. Si limitano ad aggredire cali violenti (Drop -3.5% in 10 minuti) su singole Altcoin e intascare il rimbalzo. Zero overhead Websocket.

## 🔐 LA REGOLA D'ORO (Vault del 33%)
Nessun bot può accrescere a dismisura il capitale esposto. **Ogni singolo trade chiuso in profitto** da una qualsiasi delle 40 intelligenze è tenuto per legge a dirottare il **33% dell'incasso netto verso `vault.json`** (Fondo Sicurezza Intoccabile). Il budget base libero si riduce man mano, mettendo al sicuro gli Euro faticosamente rastrellati.


