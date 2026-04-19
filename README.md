# Denaro V3 — Production Branch

## ⚠️ ATTENZIONE: Readme aggiornato il 19 Apr 2026

### Stato infrastruttura (19 Apr 2026)
Questo branch Production è stato **ripulito** il 19 Apr 2026. Il sistema precedente conteneva 100+ processi Python "zombie" che consumavano risorse senza produrre alcun trade reale. Questo readme documenta lo stato attuale.

---

## 🏗️ Architettura Corretta

### nodi attivi
| Node | IP | Servizi | Stato |
|------|----|---------|-------|
| **NUVOLA** | 87.106.3.15 | denaro-telegram, denaro-crisis, denaro-guardian | ✅ Attivo |
| **MC2** | 93.43.252.114 | LegionManager (Docker) | ✅ Attivo |
| **MarcoDG1** | 87.106.222.123 | denaro-grid-eth, denaro-grid-bnb | ⚠️ SSH fallisce |

### Servizi REALI (in Docker)
- **denaro-telegram** (NUVOLA): Notifiche Telegram reali
- **denaro-crisis** (NUVOLA): Monitor equity €435, Circuit Breaker
- **denaro-guardian** (NUVOLA): FleetGuardian V2 — self-healing dei container
- **legion-manager-prod** (MC2): 28 bot ascoltano WebSocket Binance su 28 coppie

### Zombie eliminati (19 Apr 2026)
I seguenti processi NON erano in Docker, NON producevano trade, e sono stati eliminati:
- sniper_squad, gariban_beggar, vampire_grid, scavenger_doge, tsunami_rider
- hunter_swarm, lite_guardian, orbital_websocket, dashboard_server
- whatsapp_receiver, hermes_chat_bot, crisis_manager (root), telegram_bot_interactive (root)
- fleet_guardian_v2 (root), e 80+ altri processi Python zombie

**SOLO** i servizi in Docker (3 su NUVOLA + 1 su MC2) sono operativi.

---

## 📊 Capitale Reale (19 Apr 2026)

### MC2 (Binance Spot)
| Asset | Qtà | Valore EUR |
|-------|-----|-----------|
| ETH | 0.0286 | €250.14 |
| AVAX | 5.80 | €202.99 |
| SOL | 0.975 | €170.60 |
| LINK | 4.99 | €89.81 |
| DOT | 4.91 | €60.38 |
| DOGE | 123.27 | €22.19 |
| EUR | 149.31 | €149.31 |
| BTC | 0.00002 | €1.75 |
| ADA | 0.089 | €0.05 |
| **TOTALE** | | **€947.24** |

> ⚠️ Il crisis manager mostrava €435 perché leggeva solo EUR — il capitale reale è ~€947 (comprende tutti gli asset).

### NUVOLA
- denaro-crisis: Equity ~€435 (calcolato su EUR + asset liberi)
- Nota: API Binance non disponibile per lettura diretta da questo terminale

---

## 🤖 Bot Attivi

### LegionManager (MC2 — Docker)
- 28 coppie: matic, mkru, uni, algo, chz, ftm, gala, bch, ada, link, etc, avax, near, xtz, vet, aave, dot, sand, mana, fil, xlm, enj, zil, bat, eos, ltc, axs, atom
- WebSocket: `!ticker@arr` connesso a Binance
- Max Exposure: $200 USDT globale
- Max Posizioni simultanee: 6
- Circuit Breaker: -5% daily loss
- **Stato**: In ascolto, ma ZERE posizioni aperte e ZERI trade — il vault.json è vuoto quindi i bot non hanno capitale allocato

### Grid Bot (MarcoDG1)
- **denaro-grid-eth**: Attivo, 3 BUY levels posti (1973, 1963, 1953 EUR)
- **denaro-grid-bnb**: Container presente ma SSH a MarcoDG1 fallisce (Permission denied per marco@87.106.222.123)

---

## 🔴 Problemi Aperti

1. **Legion Manager ZERI trade**: Vault €0 → bot ascolta ma non opera. Bisogna allocare capitale reale (minimo €50-100) per attivare i trade.
2. **MarcoDG1 SSH**: `marco@87.106.222.123` rifiuta la chiave RSA. FleetGuardian non può healare i grid bot su quel nodo.
3. **Cassaforte (Vault) vuota**: Nessun profitto registrato nel sistema — nessun trade ancora chiuso con successo.
4. **NUVOLA zombie rimasti**: Alcuni processi sono ancora nello stato "zombie" (defunti ma visibili) — sono innocui, solo il kernel li tiene in tabella processi.

---

## 📁 Struttura File Essenziali

```
/home/sergio/denaro/
├── legion_manager_production.py   # Main Legion Manager (Docker: /app/)
├── vault.json                     # Capitale allocato (ora €947.24)
├── positions/                     # Directory posizioni (vuota)
├── soldi/
│   ├── cassaforte.json            # Vault alias
│   └── portfolio_pnl_realtime.json # PnL aggregato
├── docker-compose.yml             # Docker stack MC2
├── Dockerfile                     # Build LegionManager image
└── README.md                      # Questo file
```

---

## 🔧 Comandi Utili

```bash
# Verifica Docker attivi
docker ps

# Log Legion Manager
docker logs legion-manager-prod --tail 20

# Riavvia Legion Manager
docker restart legion-manager-prod

# Verifica僵尸 (NUVOLA)
ssh root@87.106.3.15 'ps aux | grep python | grep -v docker | grep -v hermes'

# Check balance MC2 (da locale)
scp /tmp/check_balance.py mc2:/tmp/check_balance.py && ssh mc2 'python3 /tmp/check_balance.py'
```

---

## 📈 Prossimi Passi

1. **Allocare capitale a LegionManager**: Aggiungere €50-100 reali a vault.json per attivare i trade
2. **Fix SSH MarcoDG1**: Aggiungere la chiave RSA di root a MarcoDG1 per FleetGuardian
3. **Monitorare Grid ETH**: Il bot su MarcoDG1 sta aspettando che ETH scenda a €1973 per comprare
4. **Verificare NUVOLA balance**: Eseguire check_balance.py dentro denaro-crisis container

---

*Last update: 2026-04-19 14:35:00+02:00*