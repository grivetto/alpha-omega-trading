#!/usr/bin/env python3
"""Denaro — rig di misura corretto per le strategie.

Perche' esiste (2026-09-17): il vecchio laboratorio (brain/strategy_lab.py)
aveva quattro difetti che insieme rendevano le sue conclusioni inutilizzabili.

1. METRICA. Lo sharpe era calcolato sull'equity ORARIA di un grid, che e'
   costante a tratti: la serie dei rendimenti e' quasi tutta zeri esatti,
   mean/std esplode e annualizzato da' valori tipo -12. Rendimento +12% con
   sharpe -4.6 non e' una strategia, e' una divisione per zero mascherata.
   Qui lo sharpe si calcola sull'equity GIORNALIERA.

2. DRAWDOWN. Il vecchio codice faceva max(1 - e/peak) con peak calcolato DOPO
   il ciclo, cioe' il picco finale: non e' un drawdown. Qui si usa il picco
   corrente.

3. FALLBACK SILENZIOSO. walk_forward_evaluate, con meno di 350 barre,
   restituiva un backtest singolo senza segnalarlo. Tutti i risultati in
   registry.json erano backtest su ~200 barre (8 giorni) presentati come
   walk-forward. Qui se i fold non si possono fare, lo si DICE e il candidato
   non e' promuovibile.

4. POSIZIONE INIZIALE. Il vecchio backtest partiva con tutto il capitale
   nell'asset (start_all_in=True): misurava buy-and-hold piu' griglia, non la
   griglia. Qui si parte FLAT, come fa il bot vero.

Aggiunta decisiva: il confronto con il buy-and-hold sullo stesso periodo
(alpha). Una strategia che fa +13% mentre l'asset fa +47% non ha un edge.

Solo stdlib.
"""
from __future__ import annotations

import csv
import math
import pathlib
import statistics as st
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

GIORNO_MS = 86_400_000


# ── dati ────────────────────────────────────────────────────────────────────

def load_csv(path) -> List[dict]:
    """CSV con header ts,o,h,l,c,v prodotto da deep_fetch.py."""
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append({"ts": int(row["ts"]), "o": float(row["o"]),
                            "h": float(row["h"]), "l": float(row["l"]),
                            "c": float(row["c"]), "v": float(row["v"])})
            except (KeyError, TypeError, ValueError):
                continue
    out.sort(key=lambda c: c["ts"])
    return out


# ── indicatori (minimi, senza dipendenze) ───────────────────────────────────

def ema(values: Sequence[float], period: int) -> List[float]:
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append((v - out[-1]) * k + out[-1])
    return out


def rsi(values: Sequence[float], period: int = 14) -> List[float]:
    n = len(values)
    out = [50.0] * n
    if n <= period:
        return out
    guadagni = perdite = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        guadagni += max(d, 0.0)
        perdite += max(-d, 0.0)
    ag = guadagni / period
    ap = perdite / period
    out[period] = 100.0 if ap == 0 else 100.0 - 100.0 / (1.0 + ag / ap)
    for i in range(period + 1, n):
        d = values[i] - values[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        ap = (ap * (period - 1) + max(-d, 0.0)) / period
        out[i] = 100.0 if ap == 0 else 100.0 - 100.0 / (1.0 + ag / ap)
    return out


def adx_wilder(highs, lows, closes, period: int = 14) -> List[float]:
    n = len(closes)
    out = [0.0] * n
    if n <= period * 2:
        return out
    tr, pdm, ndm = [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
        up, dn = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        ndm[i] = dn if (dn > up and dn > 0) else 0.0
    atr = sum(tr[1:period + 1]) / period
    ap = sum(pdm[1:period + 1]) / period
    an = sum(ndm[1:period + 1]) / period
    dxs = []
    for i in range(period + 1, n):
        atr = (atr * (period - 1) + tr[i]) / period
        ap = (ap * (period - 1) + pdm[i]) / period
        an = (an * (period - 1) + ndm[i]) / period
        if atr <= 0:
            dxs.append(0.0)
            continue
        pdi, ndi = 100.0 * ap / atr, 100.0 * an / atr
        s = pdi + ndi
        dxs.append(0.0 if s <= 0 else 100.0 * abs(pdi - ndi) / s)
        if len(dxs) >= period:
            out[i] = sum(dxs[-period:]) / period
    return out


def slippage(notional: float, vol_medio_eur: float, k: float = 0.02,
             floor: float = 0.0002, cap: float = 0.005) -> float:
    """Impatto sul book: k*sqrt(notional/volume). Adverse selection. """
    if vol_medio_eur <= 0 or notional <= 0:
        return floor
    return min(cap, max(floor, k * math.sqrt(notional / vol_medio_eur)))


# ── risultato e metriche ────────────────────────────────────────────────────

@dataclass
class Risultato:
    nome: str
    capitale: float
    equity: List[float] = field(default_factory=list)
    ts: List[int] = field(default_factory=list)
    trade_pnls: List[float] = field(default_factory=list)
    fee_pagate: float = 0.0
    lordo: float = 0.0
    esposizione_bar: int = 0
    barre: int = 0
    errore: str = ""

    # ---- metriche derivate ----
    @property
    def ritorno(self) -> float:
        return (self.equity[-1] / self.capitale - 1.0) if self.equity else 0.0

    @property
    def max_dd(self) -> float:
        """Drawdown massimo sul PICCO CORRENTE (non sul picco finale)."""
        picco = -1e18
        mdd = 0.0
        for e in self.equity:
            if e > picco:
                picco = e
            if picco > 0:
                mdd = max(mdd, 1.0 - e / picco)
        return mdd

    @property
    def equity_giornaliera(self) -> List[float]:
        """Ultimo valore di equity per giorno UTC. Elimina gli zeri orari."""
        giorni: Dict[int, float] = {}
        for t, e in zip(self.ts, self.equity):
            giorni[t // GIORNO_MS] = e
        return [giorni[k] for k in sorted(giorni)]

    @property
    def rendimenti_giornalieri(self) -> List[float]:
        d = self.equity_giornaliera
        return [d[i] / d[i - 1] - 1.0 for i in range(1, len(d)) if d[i - 1] > 0]

    @property
    def sharpe(self) -> float:
        """Annualizzato sui rendimenti GIORNALIERI (365 giorni, cripto)."""
        r = self.rendimenti_giornalieri
        if len(r) < 10:
            return 0.0
        m = st.mean(r)
        sd = st.stdev(r)
        return (m / sd * math.sqrt(365.0)) if sd > 0 else 0.0

    @property
    def sortino(self) -> float:
        r = self.rendimenti_giornalieri
        if len(r) < 10:
            return 0.0
        neg = [x for x in r if x < 0]
        if not neg:
            return 0.0
        dd = math.sqrt(sum(x * x for x in neg) / len(neg))
        return (st.mean(r) / dd * math.sqrt(365.0)) if dd > 0 else 0.0

    @property
    def calmar(self) -> float:
        return (self.ritorno / self.max_dd) if self.max_dd > 0 else 0.0

    @property
    def trade(self) -> int:
        return len(self.trade_pnls)

    @property
    def win_rate(self) -> float:
        if not self.trade_pnls:
            return 0.0
        return sum(1 for x in self.trade_pnls if x > 0) / len(self.trade_pnls)

    @property
    def expectancy(self) -> float:
        return st.mean(self.trade_pnls) if self.trade_pnls else 0.0

    @property
    def fee_su_lordo_pct(self) -> float:
        if self.lordo <= 0:
            return 0.0
        return 100.0 * self.fee_pagate / self.lordo

    @property
    def esposizione_pct(self) -> float:
        return 100.0 * self.esposizione_bar / self.barre if self.barre else 0.0


def buy_and_hold(candles: List[dict], da: int = 0) -> float:
    """Rendimento del semplice buy-and-hold sulla stessa finestra."""
    if len(candles) - da < 2:
        return 0.0
    return candles[-1]["c"] / candles[da]["c"] - 1.0


# ── motori di backtest (partono FLAT, come il bot vero) ─────────────────────

def _media_volumi(candles, i, finestra=20) -> float:
    lo = max(0, i - finestra)
    return sum(candles[j]["v"] * candles[j]["c"] for j in range(lo, i)) / max(1, i - lo)


def backtest_grid(candles: List[dict], p: Dict, capitale: float = 100.0,
                  fee: float = 0.001, slippage_k: float = 0.02) -> Risultato:
    """Griglia FLAT->long, SENZA look-ahead.

    Disciplina temporale (il difetto che gonfiava i risultati):
    - gli ordini si piazzano/aggiornano sul CLOSE della barra i e diventano
      attivi dalla barra i+1 ("attivo_da");
    - i fill si controllano SOLO su ordini gia' attivi;
    - un sell nasce dal fill di un buy e diventa attivo dalla barra SUCCESSIVA.
    Senza questo, una candela con low sotto il livello e high sopra il target
    chiude un ciclo completo usando entrambi gli estremi della stessa barra:
    profitto garantito e finto.
    """
    livelli = int(p.get("levels", 3))
    d = float(p.get("buy_distance", 0.01))
    step = float(p.get("level_step", 0.005))
    tp = float(p.get("profit_target", 0.015))
    fee_buf = float(p.get("fee_buffer", 0.01))
    stop_loss = float(p.get("stop_loss", 0.0))
    filtro_ema = int(p.get("trend_ema", 0))
    adx_soglia = float(p.get("adx_threshold", 0.0))
    riancora = float(p.get("reanchor_pct", 0.004))

    closes = [c["c"] for c in candles]
    ema_l = ema(closes, filtro_ema) if filtro_ema else []
    adx_l = adx_wilder([c["h"] for c in candles], [c["l"] for c in candles], closes) \
        if adx_soglia else []
    inizio = max(filtro_ema, 20, 15)

    r = Risultato(nome=p.get("strategy", "grid"), capitale=capitale)
    cash = capitale
    asset = 0.0
    avg_cost = 0.0
    per_livello = capitale / max(1, livelli) * (1.0 - fee_buf)
    open_buys: List[dict] = []
    open_sells: List[dict] = []
    picco = capitale

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = _media_volumi(candles, i)

        # 1) fill dei BUY gia' attivi
        for ob in list(open_buys):
            if ob["attivo_da"] > i or lo > ob["price"]:
                continue
            amount = ob["amount"]
            sl = slippage(amount * ob["price"], vol_med, slippage_k)
            costo = amount * ob["price"] * (1.0 + fee + sl)
            if cash < costo:
                continue
            vecchio = asset
            cash -= costo
            asset += amount
            avg_cost = ((avg_cost * vecchio) + costo) / asset if asset else 0.0
            r.fee_pagate += amount * ob["price"] * fee
            open_buys.remove(ob)
            # il sell nasce DOPO questa barra
            open_sells.append({"price": ob["price"] * (1.0 + tp),
                               "amount": amount, "attivo_da": i + 1})

        # 2) fill dei SELL gia' attivi
        for os_ in list(open_sells):
            if os_["attivo_da"] > i or hi < os_["price"]:
                continue
            if asset < os_["amount"] - 1e-12:
                open_sells.remove(os_)
                continue
            amount = os_["amount"]
            sl = slippage(amount * os_["price"], vol_med, slippage_k)
            incasso = amount * os_["price"] * (1.0 - fee - sl)
            asset -= amount
            cash += incasso
            r.trade_pnls.append(incasso - amount * avg_cost)
            r.fee_pagate += amount * os_["price"] * fee
            open_sells.remove(os_)

        if asset <= 1e-12:
            asset = 0.0
            avg_cost = 0.0

        equity = cash + asset * price
        r.equity.append(equity)
        r.ts.append(c["ts"])
        if asset > 0:
            r.esposizione_bar += 1
        if equity > picco:
            picco = equity

        # 3) stop loss sul picco CORRENTE
        if stop_loss > 0 and equity < picco * (1.0 - stop_loss):
            break

        # 4) piazzamento/riancoraggio: usa il close, attivo dalla barra dopo
        bloccato = False
        if filtro_ema and i < len(ema_l):
            if adx_soglia > 0:
                if i < len(adx_l) and adx_l[i] >= adx_soglia and price < ema_l[i]:
                    bloccato = True
            elif price < ema_l[i]:
                bloccato = True

        desiderati = [price * (1.0 - d - lvl * step) for lvl in range(livelli)]
        for ob in list(open_buys):
            vicino = any(abs(ob["price"] - t) / t <= riancora
                         for t in desiderati if t > 0)
            if bloccato or not vicino:
                open_buys.remove(ob)
        if not bloccato:
            for t in desiderati:
                if t <= 0 or len(open_buys) >= livelli:
                    continue
                if any(abs(ob["price"] - t) / t <= riancora for ob in open_buys):
                    continue
                open_buys.append({"price": t, "amount": per_livello / t,
                                  "attivo_da": i + 1})

    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


def backtest_momentum(candles: List[dict], p: Dict, capitale: float = 100.0,
                      fee: float = 0.001, slippage_k: float = 0.02) -> Risultato:
    """Trend following a posizione singola, senza look-ahead.

    Il segnale nasce sul CLOSE della barra i; l'ingresso avviene all'OPEN della
    barra i+1 (con slippage avverso). L'uscita si valuta dalla barra di
    ingresso in poi, quando la posizione esiste davvero.
    """
    fast = int(p.get("fast_period", 8))
    slow = int(p.get("slow_period", 21))
    tp = float(p.get("profit_target", 0.02))
    slip_in = float(p.get("entry_slip", 0.002))
    rsi_conf = float(p.get("rsi_confirm", 50.0))
    stop = float(p.get("stop_loss", 0.10))
    max_hold = int(p.get("max_hold", 96))
    fee_buf = float(p.get("fee_buffer", 0.01))

    closes = [c["c"] for c in candles]
    ef, es = ema(closes, fast), ema(closes, slow)
    rl = rsi(closes, 14)
    inizio = max(slow, 15)

    r = Risultato(nome="momentum", capitale=capitale)
    cash = capitale
    asset = 0.0
    entry = 0.0
    barre_in_pos = 0
    pending = False

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = _media_volumi(candles, i)

        # ingresso deciso ieri, eseguito all'open di oggi
        if pending and asset <= 1e-12:
            prezzo_entry = c["o"] * (1.0 + slip_in)
            budget = cash * (1.0 - fee_buf)
            if prezzo_entry > 0 and budget > 0:
                qty = budget / prezzo_entry
                sl = slippage(qty * prezzo_entry, vol_med, slippage_k)
                costo = qty * prezzo_entry * (1.0 + fee + sl)
                if costo <= cash:
                    cash -= costo
                    asset = qty
                    entry = prezzo_entry
                    r.fee_pagate += qty * prezzo_entry * fee
                    barre_in_pos = 0
            pending = False

        if asset > 1e-12:
            barre_in_pos += 1
            uscita = None
            target = entry * (1.0 + tp)
            if hi >= target:
                uscita = target
            elif stop > 0 and lo <= entry * (1.0 - stop):
                uscita = entry * (1.0 - stop)
            elif barre_in_pos >= max_hold:
                uscita = price
            if uscita:
                sl = slippage(asset * uscita, vol_med, slippage_k)
                incasso = asset * uscita * (1.0 - fee - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * entry)
                r.fee_pagate += asset * uscita * fee
                asset = 0.0
                barre_in_pos = 0

        # segnale sul close di OGGI -> ingresso domani
        if asset <= 1e-12 and not pending and ef[i] > es[i] and rl[i] >= rsi_conf:
            pending = True

        equity = cash + asset * price
        r.equity.append(equity)
        r.ts.append(c["ts"])
        if asset > 0:
            r.esposizione_bar += 1

    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


def backtest_meanrev(candles: List[dict], p: Dict, capitale: float = 100.0,
                     fee: float = 0.001, slippage_k: float = 0.02) -> Risultato:
    """Mean reversion a posizione singola, senza look-ahead (stessa disciplina)."""
    periodo = int(p.get("rsi_period", 14))
    os_soglia = float(p.get("rsi_oversold", 30.0))
    rsi_exit = float(p.get("rsi_exit", 55.0))
    tp = float(p.get("profit_target", 0.015))
    slip_in = float(p.get("entry_slip", 0.001))
    max_dev = float(p.get("max_dev_from_mean", 0.05))
    ma_n = int(p.get("ma_period", 21))
    stop = float(p.get("stop_loss", 0.10))
    fee_buf = float(p.get("fee_buffer", 0.01))

    closes = [c["c"] for c in candles]
    rl = rsi(closes, periodo)
    inizio = max(ma_n, periodo) + 1

    r = Risultato(nome="meanrev", capitale=capitale)
    cash = capitale
    asset = 0.0
    entry = 0.0
    pending = False

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = _media_volumi(candles, i)

        if pending and asset <= 1e-12:
            prezzo_entry = c["o"] * (1.0 - slip_in)
            budget = cash * (1.0 - fee_buf)
            if prezzo_entry > 0 and budget > 0:
                qty = budget / prezzo_entry
                sl = slippage(qty * prezzo_entry, vol_med, slippage_k)
                costo = qty * prezzo_entry * (1.0 + fee + sl)
                if costo <= cash:
                    cash -= costo
                    asset = qty
                    entry = prezzo_entry
                    r.fee_pagate += qty * prezzo_entry * fee
            pending = False

        if asset > 1e-12:
            uscita = None
            target = entry * (1.0 + tp)
            if hi >= target:
                uscita = target
            elif rl[i] >= rsi_exit:
                uscita = price
            elif stop > 0 and lo <= entry * (1.0 - stop):
                uscita = entry * (1.0 - stop)
            if uscita:
                sl = slippage(asset * uscita, vol_med, slippage_k)
                incasso = asset * uscita * (1.0 - fee - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * entry)
                r.fee_pagate += asset * uscita * fee
                asset = 0.0

        if asset <= 1e-12 and not pending:
            media = sum(closes[i - ma_n:i]) / ma_n
            dev = (media - price) / media if media > 0 else 0.0
            if rl[i] < os_soglia and 0 < dev <= max_dev:
                pending = True

        equity = cash + asset * price
        r.equity.append(equity)
        r.ts.append(c["ts"])
        if asset > 0:
            r.esposizione_bar += 1

    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


MOTORI: Dict[str, Callable] = {
    "grid": backtest_grid,
    "momentum": backtest_momentum,
    "meanrev": backtest_meanrev,
}


# ── walk-forward con fold OOS espliciti ─────────────────────────────────────

@dataclass
class Fold:
    indice: int
    train_da: int
    train_a: int
    test_da: int
    test_a: int
    ritorno_train: float
    ritorno_test: float
    dd_test: float
    trade_test: int
    bh_test: float

    @property
    def alpha_test(self) -> float:
        return self.ritorno_test - self.bh_test


def walk_forward(candles: List[dict], motore: str, griglia: List[Dict],
                 capitale: float = 100.0, fee: float = 0.001,
                 barre_train: int = 2000, barre_test: int = 1000,
                 passo: Optional[int] = None,
                 slippage_k: float = 0.02) -> Tuple[List[Fold], Dict, str]:
    """Ottimizza SOLO sul train, valuta SOLO sul test, per ogni fold.

    Ritorna (fold, parametri_migliori, motivo). Se i fold non sono possibili
    lo DICE: il vecchio lab restituiva un backtest singolo in silenzio ed e'
    quello che ha reso inutili tutti i risultati precedenti.
    """
    fn = MOTORI[motore]
    n = len(candles)
    bisogno = barre_train + barre_test
    if n < bisogno + 50:
        return [], {}, ("DATI INSUFFICIENTI per la walk-forward: servono %d barre, "
                        "disponibili %d" % (bisogno + 50, n))
    passo = passo or barre_test
    folds: List[Fold] = []
    inizio = 0
    idx = 0
    while inizio + bisogno <= n:
        tr_da, tr_a = inizio, inizio + barre_train
        te_da, te_a = tr_a, tr_a + barre_test
        # --- ottimizzazione sul TRAIN ---
        migliore, miglior_punteggio = None, -1e18
        for p in griglia:
            res = fn(candles[tr_da:tr_a], p, capitale, fee, slippage_k)
            if res.trade < 5:
                continue
            punteggio = res.ritorno - 1.0 * res.max_dd
            if punteggio > miglior_punteggio:
                migliore, miglior_punteggio = p, punteggio
        if migliore is None:
            inizio += passo
            continue
        # --- valutazione sul TEST (out-of-sample, parametri congelati) ---
        rt = fn(candles[tr_da:tr_a], migliore, capitale, fee, slippage_k)
        te = fn(candles[te_da:te_a], migliore, capitale, fee, slippage_k)
        folds.append(Fold(indice=idx, train_da=tr_da, train_a=tr_a,
                          test_da=te_da, test_a=te_a,
                          ritorno_train=rt.ritorno, ritorno_test=te.ritorno,
                          dd_test=te.max_dd, trade_test=te.trade,
                          bh_test=buy_and_hold(candles, te_da)))
        idx += 1
        inizio += passo
    if not folds:
        return [], {}, "nessun fold producibile con questa griglia"
    return folds, {}, ""


# ── punteggio di robustezza (sostituisce score()) ───────────────────────────

@dataclass
class Valutazione:
    simbolo: str
    motore: str
    barre_totali: int
    fold: List[Fold]
    migliore_params: Dict
    motivo: str
    ritorno_intero: float
    alpha_intero: float
    dd_intero: float
    sharpe_intero: float
    trade_intero: int
    fee_su_lordo: float
    esposizione: float

    @property
    def fold_positivi(self) -> float:
        if not self.fold:
            return 0.0
        return sum(1 for f in self.fold if f.ritorno_test > 0) / len(self.fold)

    @property
    def fold_alpha_positivi(self) -> float:
        if not self.fold:
            return 0.0
        return sum(1 for f in self.fold if f.alpha_test > 0) / len(self.fold)

    @property
    def mediana_oos(self) -> float:
        return st.median([f.ritorno_test for f in self.fold]) if self.fold else 0.0

    @property
    def mediana_alpha(self) -> float:
        return st.median([f.alpha_test for f in self.fold]) if self.fold else 0.0

    @property
    def dispersione_oos(self) -> float:
        if len(self.fold) < 2:
            return 0.0
        return st.pstdev([f.ritorno_test for f in self.fold])

    @property
    def trade_oos(self) -> int:
        return sum(f.trade_test for f in self.fold)

    @property
    def robusto(self) -> bool:
        """Il gate: non basta un buon numero, serve che regga FUORI campione."""
        # Serve anche l'alpha: una strategia che perde contro il semplice
        # buy-and-hold NON e' un edge, per quanti fold positivi abbia. Senza
        # questo requisito il gate promuoveva rumore con segno favorevole
        # (caso ETH-EUR, 1H: 75% fold positivi ma alpha -2.5%).
        return (len(self.fold) >= 3 and self.fold_positivi >= 0.75
                and self.mediana_oos > 0 and self.mediana_alpha > 0
                and self.trade_oos >= 30)

    def riga(self) -> str:
        return ("%-9s %-9s fold=%2d pos=%4.0f%% medOOS=%+6.2f%% disp=%5.2f%% "
                "alphaOOS=%+6.2f%% trOOS=%4d | intero ret=%+7.2f%% alpha=%+7.2f%% "
                "dd=%5.1f%% sh=%5.2f tr=%4d feeL=%5.1f%% %s"
                % (self.simbolo, self.motore, len(self.fold),
                   100 * self.fold_positivi, 100 * self.mediana_oos,
                   100 * self.dispersione_oos, 100 * self.mediana_alpha,
                    self.trade_oos, 100 * self.ritorno_intero,
                   100 * self.alpha_intero, 100 * self.dd_intero,
                    self.sharpe_intero, self.trade_intero, self.fee_su_lordo,
                    "ROBUSTO" if self.robusto else ""))


def valuta(simbolo: str, candles: List[dict], motore: str, griglia: List[Dict],
           capitale: float = 100.0, fee: float = 0.001,
           barre_train: int = 2000, barre_test: int = 1000,
           slippage_k: float = 0.02) -> Valutazione:
    """Walk-forward + valutazione sull'intero periodo, con il gate OOS."""
    fold, _, motivo = walk_forward(candles, motore, griglia, capitale, fee,
                                   barre_train, barre_test, slippage_k=slippage_k)
    # miglior parametro sull'INTERO periodo (solo per il report, non per il gate)
    fn = MOTORI[motore]
    migliore, miglior_p = None, -1e18
    for p in griglia:
        res = fn(candles, p, capitale, fee, slippage_k)
        if res.trade < 5:
            continue
        punteggio = res.ritorno - 1.0 * res.max_dd
        if punteggio > miglior_p:
            migliore, miglior_p = p, punteggio
    if migliore is None:
        return Valutazione(simbolo, motore, len(candles), fold, {}, 
                           motivo or "nessun parametro con abbastanza trade",
                           0, 0, 0, 0, 0, 0, 0)
    r = fn(candles, migliore, capitale, fee, slippage_k)
    bh = buy_and_hold(candles)
    if r.trade == 0:
        return Valutazione(simbolo, motore, len(candles), fold, migliore,
                           "NESSUN TRADE sull'intero periodo: i parametri "
                           "migliori in-sample non operano (caso degenere)",
                           0.0, 0.0, 0.0, 0.0, 0, 0.0, 0.0)
    return Valutazione(simbolo=simbolo, motore=motore, barre_totali=len(candles),
                       fold=fold, migliore_params=migliore, motivo=motivo,
                       ritorno_intero=r.ritorno, alpha_intero=r.ritorno - bh,
                       dd_intero=r.max_dd, sharpe_intero=r.sharpe,
                       trade_intero=r.trade, fee_su_lordo=r.fee_su_lordo_pct,
                       esposizione=r.esposizione_pct)
