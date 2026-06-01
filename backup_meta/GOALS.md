# 📐 Goal Definition — Denaro Self-Improvement System

> *"What is success? What is failure? Define it, score it, improve it."*

## Bot Goals

### Stellatron (ADA/EUR Grid)

| Metrica | Target | Peso | Fallimento | Note |
|---------|--------|------|------------|------|
| Win Rate | >60% | 25% | <40% | Su 30+ trades |
| Sharpe Ratio (mensile) | >1.0 | 30% | <0.3 | PnL / std(PnL) approssimato |
| Drawdown Massimo | <8% | 20% | >15% | Su portafoglio allocato |
| Trades/giorno | 5-20 | 10% | <2 o >40 | Attività sana |
| Profit (30gg) | +5% | 15% | -3% | Rendimento sul capitale allocato |

### Orion (BTC/EUR Swing)

| Metrica | Target | Peso | Fallimento | Note |
|---------|--------|------|------------|------|
| Win Rate | >55% | 20% | <35% | Su 15+ trades |
| Sharpe Ratio (mensile) | >0.8 | 25% | <0.2 | Su tutti i trade chiusi |
| Drawdown Massimo | <10% | 20% | >18% | Peak-to-trough |
| Profit Factor | >1.5 | 20% | <1.0 | Gross PnL / Gross Loss |
| Profit (30gg) | +8% | 15% | -5% | Rendimento sul capitale allocato |

### Squadra (Ares/Hermes/Apollo/Artemis)

| Metrica | Target | Peso | Fallimento | Note |
|---------|--------|------|------------|------|
| Win Rate | >55% | 20% | <35% | Media sui 4 bot |
| Sharpe Ratio (mensile) | >0.8 | 25% | <0.2 | Aggregato su portafoglio |
| Drawdown Massimo | <12% | 20% | >20% | Su portafoglio totale |
| Capitale Sotto Gestione | Stabile o + | 15% | -10%/mese | Variazione capitale allocato |
| Profit (30gg) | +6% | 20% | -4% | Su portafoglio totale |

### Marco (SOL/EUR Grid)

| Metrica | Target | Peso | Fallimento | Note |
|---------|--------|------|------------|------|
| Win Rate | >55% | 25% | <35% | Su 20+ trades |
| Sharpe Ratio (mensile) | >0.8 | 25% | <0.2 | Su tutti i trade chiusi |
| Drawdown Massimo | <10% | 20% | >15% | Peak-to-trough |
| Trades/giorno | 5-30 | 10% | <2 o >50 | Attività sana |
| Profit (30gg) | +5% | 20% | -4% | Rendimento sul capitale allocato |

## Scoring

Ogni trade e ogni bot riceve uno score combinato 0-100:
```
score = sum(metric_score * peso per ogni metrica)
```
dove `metric_score` è 0 (fallimento) → 50 (neutro) → 100 (target superato).

### Regole di Intervento

| Score | Stato | Azione |
|-------|-------|--------|
| ≥75 | ✅ Verde | Mantieni parametri |
| 50-74 | 🟡 Giallo | Osserva, riduci sizing del 20% |
| 30-49 | 🟠 Arancione | Rivedi parametri, stop parziale |
| <30 | 🔴 Rosso | Stop bot, review urgente |

## Review Cycle

- **Giornaliera**: Score rapido, alert via dashboard
- **Settimanale**: Review completa con raccomandazioni parametri
- **Mensile**: Deep-dive, aggiornamento GOALS.md se necessario

## Principio Scientifico

> **Cambia UNA variabile alla volta.** Misura l'impatto. Se migliora → nuova baseline. Se peggiora → rollback.

Non modificare mai più di un parametro per bot per ciclo di review, altrimenti non saprai cosa ha causato il risultato.
