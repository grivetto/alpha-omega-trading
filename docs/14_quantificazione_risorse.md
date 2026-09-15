# Quantificazione delle risorse — Denaro

> **Rilevato il 2026-09-15** con query read-only su OKX EEA e Kraken e misure
> dirette sui tre host. Prezzi di riferimento: DOGE €0,06957 · SOL €84,28 ·
> XRP €1,1044 · ADA €0,169 · USD/EUR ≈ 0,86.

---

## 1. Capitale reale disponibile

| Venue / conto | Asset | Valore € | Liquido € |
|---|---|---:|---:|
| OKX — mc2 | DOGE 262,946 + SOL 0,044987 + €0,380 | **22,46** | 0,38 |
| OKX — MARCODG1 | €1,002 + DOGE 9,980 | **1,70** | 1,00 |
| Kraken — conto unico¹ | XRP 15,827 + ADA 0,064 + €6,104 + $0,407 | **23,94** | 6,10 |
| OKX — nuvola | chiave invalida (50111) | n.d. | — |
| **TOTALE** | | **≈ €48,10** | **≈ €7,50** |

¹ `KRAKEN_API_KEY`, `NUVOLASUB1_KRAKEN_*` e `TRENDSUB_KRAKEN_*` sono **lo stesso
conto**: sommarli significherebbe contare il capitale tre volte.

**Ordini aperti dopo la riconciliazione del 2026-09-15** (12 ordini morti
annullati su OKX):

| Venue | Ordine | Notional |
|---|---|---:|
| OKX mc2 | DOGE sell 131,47 @ 0,07104 · 131,47 @ 0,07174 | €18,68 · €18,87 |
| OKX mc2 | SOL sell 0,0225 @ 86,06 · 0,0225 @ 86,90 | €1,94 · €1,96 |
| Kraken | XRP sell 5,259 @ 1,23287 · 5,278 @ 1,22845 · 5,289 @ 1,22584 | €6,48 · €6,48 · €6,48 |

Tutto l'inventario è impegnato in vendite: **il sistema è strutturalmente
sell-only** finché non entra capitale liquido.

---

## 2. Infrastruttura

| Host | CPU | Core | RAM | Disco usato | Load | Ruolo |
|---|---|---:|---:|---:|---:|---|
| **mc2** | Intel N150 (mini-PC) | 4 | 15,4 GB | 124/916 GB (15%) | 0,75 | nodo live OKX, Zabbix, feeder, dashboard, AI bridge, desktop |
| **nuvola** | AMD EPYC-Milan (VPS) | 4 | 3,7 GB | 9,1/116 GB (8%) | 0,24 | idle (chiavi OKX invalide) |
| **MARCODG1** | AMD EPYC-Milan (VPS) | 4 | 3,8 GB | 54/116 GB (47%) | 0,09 | nodo live Kraken, dashboard pubblica, Zabbix web |
| **Totale** | | **12** | **22,9 GB** | **187/1.148 GB** | | |

**Consumo reale del trading:** 3 processi `denaro_node` ≈ **0,8 GB di RAM e
meno del 3% di CPU complessiva**. Un solo processo gestisce N bot in asyncio:
il costo marginale di aggiungere un bot è praticamente nullo.

> **L'infrastruttura non è il collo di bottiglia.** Reggerebbe 50-100 bot senza
> modifiche. Il costo marginale di scalare da €48 a €500 è **zero**.

---

## 3. Vincoli di mercato misurati (non stimati)

| Venue | Coppia | Min. quantità | Min. notional | Maker | Taker | Costo ciclo (maker) | Costo ciclo (taker) |
|---|---|---:|---:|---:|---:|---:|---:|
| OKX | DOGE/EUR | 10 | ~€0,70 | 0,08% | 0,10% | **0,16%** | 0,20% |
| OKX | SOL/EUR | 0,01 | ~€0,84 | 0,08% | 0,10% | **0,16%** | 0,20% |
| Kraken | XRP/EUR | 1,65 | €0,45 | 0,16% | 0,26% | **0,32%** | 0,52% |
| Kraken | SOL/EUR | 0,06 | €0,45 | 0,16% | 0,26% | **0,32%** | 0,52% |
| Kraken | ADA/EUR | 20 | €0,45 | 0,16% | 0,26% | **0,32%** | 0,52% |

### Due correzioni a costo zero

1. **I config Kraken usano `fee: 0.0026` (taker).** La griglia piazza ordini
   **limite**: il taker non si applica. Usare 0,0016 (−38% di fee drag) è più
   corretto e, su un ciclo da 2%, porta il netto da 1,48% a 1,68%.
2. **OKX ha minimi 10 volte più bassi di Kraken** (€0,84 vs €5,05 su SOL). A
   parità di capitale, OKX consente livelli più fitti e quindi più cicli.

---

## 4. Il conto economico reale (misurato, non stimato)

Cronologia ordini del conto OKX di mc2, dall'apertura al 2026-09-15:

| Coppia | Trade | Comprato | Venduto | Prezzo medio buy | Prezzo medio sell | Fee |
|---|---:|---:|---:|---:|---:|---:|
| DOGE/EUR | 11 | €24,00 | €7,78 | 0,076040 | 0,076277 | €0,6496 |
| SOL/EUR | 16 | €20,00 | €16,35 | 88,24998 | 90,22515 | €0,0331 |

- **Guadagno lordo sui round-trip: €0,382**
- **Commissioni pagate: €0,683**
- **Risultato netto: −€0,30**

> Il sistema ha indovinato la direzione su entrambe le coppie (venduto più caro
> di quanto ha comprato) e ha comunque **perso**, perché ha pagato €1,79 di fee
> per ogni euro di margine lordo. Questo è il numero che la dashboard non ha mai
> mostrato.

---

## 5. Cosa serve davvero per i €500

### 5.1 Vincoli da rispettare

| Vincolo | Valore | Soddisfatto con €500? |
|---|---|---|
| Min. notional per livello | €0,84 (OKX) | ✅ con 5 livelli su €166/bot → €33/livello (40× il minimo) |
| Fee per ciclo | 0,16% (OKX maker) | ✅ spaziatura 1,5-2,5% ≫ 0,16% |
| RAM/CPU | 0,8 GB, <3% | ✅ nessuna modifica necessaria |
| Numero di conti | 1 engine per conto | ⚠️ oggi i conti sono 3 e vanno consolidati |

### 5.2 L'unico vincolo che i €500 NON risolvono

Il backtest a parità live (`docs/10_backtest_onesto_e_findings.md`) su 1 anno
di dati reali dà **alpha negativo in tutti i regimi testati**:

| Regime | Grid SOL/EUR | Buy&hold | Alpha |
|---|---:|---:|---:|
| Rialzo | +12,98% | +34,77% | **−21,79%** |
| Ribasso | −25,22% | −24,18% | −1,03% |
| Ribasso | −25,51% | −27,03% | +1,52% |
| Crash | −44,05% | −46,85% | +2,79% |

In salita la griglia rinuncia a ~22 punti; in discesa perde quasi quanto il
mercato. **Più capitale non crea un edge: moltiplica il risultato di un edge
che oggi non esiste.** Con €500 gli stessi numeri diventano ±€125-225 di
drawdown, che è 25-45% del capitale — non il 2% autorizzato.

### 5.3 Il 2% di rischio è incompatibile con una griglia

Una griglia non ha uno stop al 2%: il suo rischio è **l'intero inventario**
durante un trend ribassista. Il budget del 2% (€0,96 su €48, €10 su €500) è
significativo solo per una strategia **con stop-loss esplicito** (momentum con
trailing stop), non per una strategia che accumula l'asset che scende.

**Conseguenza operativa:** o si accetta che il rischio è l'inventario e lo si
dimensiona su quanto si è disposti a perdere, oppure si cambia strategia.

### 5.4 Allocazione proposta per €500

| Voce | Importo | Motivo |
|---|---:|---|
| Conto unico OKX (EEA) | €500 | minimi bassi, fee maker 0,08%, un solo engine |
| 3 bot × 5 livelli: SOL, XRP, ADA | €150/bot | DOGE escluso (backtest −4/−5%) |
| Riserva non allocata | €50 | margine per il prelievo/ribilanciamento |
| Nuvola | dismettere o ri-chiavizzare | oggi non produce nulla |

Costo infrastrutturale aggiuntivo: **€0**. Config pronta: vedi §6.

---

## 6. Aspettativa onesta sui €500

| Scenario | Rendimento 90gg | Risultato su €500 | Note |
|---|---:|---:|---|
| Regime favorevole | +8 ÷ +12% | **+€40 ÷ +€60** | come il backtest nei periodi di rialzo |
| Regime laterale | −2 ÷ +3% | **−€10 ÷ +€15** | le fee erodono il margine |
| Regime ribassista | −25 ÷ −45% | **−€125 ÷ −€225** | l'inventario resta esposto |
| Buy&hold di riferimento | — | beta di mercato − fee | la griglia non ha battuto questo |

**Sintesi:** €500 rendono il sistema *operabile e misurabile*, non
automaticamente *profittevole*. Il valore di questa fase è costruire il
processo che distingue un edge reale da una sequenza fortunata — che è
esattamente ciò che manca da un anno.

---

## 7. Cosa è stato corretto su mc2 il 2026-09-15

| # | Problema | Prima | Dopo |
|---|---|---|---|
| S1 | `zabbix-server`: syslog-ng integrato in spin | **362% CPU**, 2,37 GB RAM | 0,72% CPU, 98 MB RAM |
| S2 | `logrotate` in errore (config di backup duplicata) | /var/log = 2,5 GB | 621 MB |
| S3 | journal systemd | 1,9 GB | 393 MB |
| S4 | `certbot` falliva ogni giorno (cert. scaduto, gestito su MARCODG1) | timer attivo, fallimento quotidiano | disabilitato |
| S5 | 83 direttive AI + script di orchestrazione in `~/denaro` | disordine | archiviati |
| S6 | 12 ordini sell morti/duplicati su OKX (dal 08/09, +9÷15%) | 100% capitale congelato | annullati; griglia re-ancorata a +2/+3% |
| S7 | load average | 7,37 | **0,75** |

---

*Tutti i valori di §1 e §4 provengono da query autenticate read-only sugli
exchange. Le correzioni di §7 sono state eseguite e verificate.*
