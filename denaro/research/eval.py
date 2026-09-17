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

from denaro.domain.indicators import atr_wilder, ema_series as ema
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


def backtest_trend(candles: List[dict], p: Dict, capitale: float = 100.0,
                   fee: float = 0.001, slippage_k: float = 0.02) -> Risultato:
    """Trend following: breakout, trailing stop ATR, posizione dimensionata sul RISCHIO.

    Differenza sostanziale dal momentum naif testato in precedenza (target
    fisso, size fissa, nessun trailing):
    - si entra sul breakout del massimo delle ultime N barre (canale Donchian),
      con filtro di tendenza opzionale (solo long sopra la media lunga);
    - la size si calcola sul rischio: si perde al massimo risk_pct dell'equity
      se lo stop iniziale scatta, quindi qty = equity*risk / (stop_mult*ATR).
      Cosi' la posizione si stringe quando la volatilita' sale;
    - l'uscita e' un trailing stop a trail_mult*ATR dal massimo, non un target.
    Con fee reali a 0.20% per lato servono movimenti grandi: questa famiglia
    trada poco, ed e' esattamente cio' che serve.

    Disciplina temporale: il segnale nasce sul close della barra i e l'ingresso
    avviene all'OPEN della barra i+1. Lo stop iniziale e' fissato all'ingresso,
    quindi controllarlo sul low della stessa barra di ingresso e' lecito (la
    posizione esiste dall'apertura). Il trailing si aggiorna dopo, sul close.
    """
    canale = int(p.get("canale", 20))
    atr_n = int(p.get("atr_period", 14))
    trail = float(p.get("trail_mult", 3.0))
    rischio = float(p.get("risk_pct", 0.01))
    ema_n = int(p.get("trend_ema", 0))
    esposizione_max = float(p.get("max_exposure", 1.0))
    stop_mult = float(p.get("stop_atr_mult", 2.0))

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    atr_l = atr_wilder(highs, lows, closes, atr_n)
    ema_l = ema(closes, ema_n) if ema_n else []
    inizio = max(canale, atr_n, ema_n) + 1

    r = Risultato(nome="trend", capitale=capitale)
    cash = capitale
    asset = 0.0
    basis = 0.0
    stop = 0.0
    pending = False

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = _media_volumi(candles, i)

        # ingresso deciso ieri, eseguito all'open di oggi
        if pending and asset <= 1e-12:
            a = atr_l[i - 1]
            if a > 0 and c["o"] > 0:
                dist = stop_mult * a
                prezzo_entry = c["o"] * (1.0 + 0.0005)
                # Il cap di esposizione deve tenere conto di fee e slippage,
                # altrimenti l'ordine viene RIFIUTATO invece che ridotto alla
                # size massima affondabile: cosi' si perdono trade validi.
                qty_esposizione = (cash * esposizione_max) / prezzo_entry
                qty = min((cash * rischio) / dist, qty_esposizione)
                # Due passaggi: lo slippage dipende dal notional, quindi una
                # stima a priori resta o troppo ottimista (l'ordine viene
                # rifiutato e il trade si perde) o troppo prudente. Si calcola
                # il costo vero e si riduce la size di conseguenza.
                notional = qty * prezzo_entry
                sl = slippage(notional, vol_med, slippage_k)
                costo = notional * (1.0 + fee + sl)
                if costo > cash and costo > 0:
                    qty *= cash / costo
                    notional = qty * prezzo_entry
                    sl = slippage(notional, vol_med, slippage_k)
                    costo = notional * (1.0 + fee + sl)
                if qty > 1e-12 and costo <= cash * (1.0 + 1e-9):
                    cash -= costo
                    asset = qty
                    basis = costo / qty
                    stop = prezzo_entry - dist
                    r.fee_pagate += notional * fee
            pending = False

        # trailing stop / uscita
        if asset > 1e-12:
            if lo <= stop:
                sl = slippage(asset * stop, vol_med, slippage_k)
                incasso = asset * stop * (1.0 - fee - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * basis)
                r.fee_pagate += asset * stop * fee
                asset = 0.0
                stop = 0.0
            else:
                a = atr_l[i]
                if a > 0:
                    nuovo_stop = price - trail * a
                    if nuovo_stop > stop:
                        stop = nuovo_stop

        # segnale sul close di oggi -> ingresso domani
        if asset <= 1e-12 and not pending and i >= canale:
            massimo = max(highs[i - canale:i])
            sopra_ema = (not ema_l) or price > ema_l[i]
            if price > massimo and sopra_ema and atr_l[i] > 0:
                pending = True

        equity = cash + asset * price
        r.equity.append(equity)
        r.ts.append(c["ts"])
        if asset > 0:
            r.esposizione_bar += 1

    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


def backtest_pullback(candles: List[dict], p: Dict, capitale: float = 100.0,
                      fee: float = 0.002, slippage_k: float = 0.02,
                      fee_taker: float = 0.0035) -> Risultato:
    """Compra il RITORNO dentro un trend, con ordini LIMITE su entrambi i lati.

    Perche' esiste: il trend following classico entra sul breakout ed esce sul
    trailing stop, cioe' con ordini a MERCATO: 0.35% per lato, 0.70% di round
    trip. A quella fee il suo alpha misurato e' -1.97% (t=-0.30). Il segnale
    pero' esiste: a fee zero l'alpha e' +34.98% con t=+4.51.

    Qui si cattura lo stesso segnale pagando MAKER su entrambi i lati:
    - si entra solo se il prezzo e' SOPRA la media lunga (trend rialzista);
    - l'ingresso e' un ordine limite SOTTO il mercato: si compra sul ritorno,
      non sull'inseguimento. Un ordine limite sotto il mercato resta in book
      finche' non viene toccato, quindi e' maker (0.20%);
    - l'uscita normale e' un ordine limite SOPRA l'ingresso: maker (0.20%);
    - solo lo stop duro e il time-stop escono a mercato (taker 0.35%), e sono
      eventi rari.

    Round trip tipico: 0.40% invece di 0.70%.

    Disciplina temporale: l'ordine si piazza sul close della barra i e diventa
    attivo da i+1; si riempie solo se una barra successiva lo tocca. In caso di
    barra che tocca sia il target sia lo stop si assume che scatti PRIMA lo
    stop: scelta conservativa.
    """
    ema_n = int(p.get("trend_ema", 200))
    atr_n = int(p.get("atr_period", 14))
    entry_atr = float(p.get("entry_atr", 0.5))
    exit_atr = float(p.get("exit_atr", 2.0))
    stop_mult = float(p.get("stop_mult", 3.0))
    max_hold = int(p.get("max_hold", 42))
    rischio = float(p.get("risk_pct", 0.02))
    esp_max = float(p.get("max_exposure", 1.0))
    fee_buf = float(p.get("fee_buffer", 0.01))

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    atr_l = atr_wilder(highs, lows, closes, atr_n)
    ema_l = ema(closes, ema_n) if ema_n else []
    inizio = max(atr_n, ema_n) + 1

    r = Risultato(nome="pullback", capitale=capitale)
    cash = capitale
    asset = 0.0
    basis = 0.0
    target = 0.0
    stop = 0.0
    barre_in_pos = 0
    pending = None      # prezzo del limit buy in attesa
    pending_da = 0

    for i in range(inizio, len(candles)):
        c = candles[i]
        price, hi, lo = c["c"], c["h"], c["l"]
        vol_med = _media_volumi(candles, i)

        # --- posizione aperta: prima lo stop (conservativo), poi il target ---
        if asset > 1e-12:
            barre_in_pos += 1
            if lo <= stop:
                sl = slippage(asset * stop, vol_med, slippage_k)
                incasso = asset * stop * (1.0 - fee_taker - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * basis)
                r.fee_pagate += asset * stop * fee_taker
                asset = 0.0
            elif hi >= target:
                sl = slippage(asset * target, vol_med, slippage_k)
                incasso = asset * target * (1.0 - fee - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * basis)
                r.fee_pagate += asset * target * fee
                asset = 0.0
            elif barre_in_pos >= max_hold:
                sl = slippage(asset * price, vol_med, slippage_k)
                incasso = asset * price * (1.0 - fee_taker - sl)
                cash += incasso
                r.trade_pnls.append(incasso - asset * basis)
                r.fee_pagate += asset * price * fee_taker
                asset = 0.0

        # --- limit buy in attesa: si riempie se la barra lo tocca ---
        if asset <= 1e-12 and pending is not None and i >= pending_da and lo <= pending:
            a = atr_l[i - 1] if i - 1 >= 0 else 0.0
            qty = 0.0
            if a > 0 and pending > 0:
                qty = (cash * rischio) / (stop_mult * a)
                qty = min(qty, (cash * esp_max) / pending)
                notional = qty * pending
                sl = slippage(notional, vol_med, slippage_k)
                costo = notional * (1.0 + fee + sl)
                if costo > cash and costo > 0:
                    qty *= cash / costo
                    notional = qty * pending
                    sl = slippage(notional, vol_med, slippage_k)
                    costo = notional * (1.0 + fee + sl)
            if qty > 1e-12 and costo <= cash * (1.0 + 1e-9):
                cash -= costo
                asset = qty
                basis = costo / qty
                target = pending + exit_atr * a
                stop = pending - stop_mult * a
                barre_in_pos = 0
                r.fee_pagate += (qty * pending) * fee
            pending = None

        # --- decisione sul close: piazza il limit buy per la barra dopo ---
        if asset <= 1e-12:
            a = atr_l[i]
            trend_su = (not ema_l) or (i < len(ema_l) and price > ema_l[i])
            if a > 0 and trend_su:
                nuovo = price - entry_atr * a
                if nuovo > 0:
                    pending = nuovo
                    pending_da = i + 1
            else:
                pending = None
        else:
            pending = None

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
    "trend": backtest_trend,
    "pullback": backtest_pullback,
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
    # benchmark corretto per il rischio: esposizione media x buy&hold.
    # Se la strategia sta fuori dal mercato meta' del tempo, il confronto
    # giusto con il buy&hold e' meta' del suo rendimento, non tutto.
    bench_risk: float = 0.0

    @property
    def alpha_test(self) -> float:
        return self.ritorno_test - self.bh_test

    @property
    def alpha_risk(self) -> float:
        """Alpha contro il benchmark corretto per l'esposizione."""
        return self.ritorno_test - self.bench_risk


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


def walk_forward_portafoglio(serie: Dict[str, List[dict]], motore: str,
                             griglia: List[Dict], capitale: float = 100.0,
                             fee: float = 0.001,
                             barre_train: int = 1000, barre_test: int = 500,
                             slippage_k: float = 0.02) -> Tuple[List["Fold"], Dict, str]:
    """Walk-forward su un PORTAFOGLIO con un solo set di parametri.

    Perche' e' la misura giusta per il trend following:

    1. UN SOLO set di parametri per tutti i simboli, scelto sul train
       AGGREGATO e valutato sul test AGGREGATO. Cinque ottimizzazioni
       indipendenti su cinque asset sono cinque occasioni di overfittare; una
       sola e' una sola. E' anche cio' che si puo' fare davvero in live.
    2. Il trend following e' a coda grossa: pochi periodi molto positivi e
       molti piccoli negativi. La percentuale di fold positivi e' quindi una
       statistica povera. Conta il rendimento COMPOSTO del portafoglio e
       l'alpha contro il buy-and-hold equal-weight sugli stessi periodi.
    3. Ogni simbolo riceve 1/N del capitale (equal weight), quindi il
       rendimento di portafoglio e' la MEDIA dei rendimenti dei simboli.

    I simboli vengono allineati sulla CODA comune (stessa timeframe, stessa
    finestra), cosi' gli indici dei fold corrispondono agli stessi istanti.
    """
    fn = MOTORI[motore]
    simboli = sorted(serie)
    n_comune = min(len(serie[s]) for s in simboli)
    if n_comune < barre_train + barre_test + 50:
        return [], {}, ("dati comuni insufficienti: il simbolo piu' corto ha "
                        "%d barre, servono %d" % (n_comune, barre_train + barre_test + 50))
    dati = {s: serie[s][-n_comune:] for s in simboli}
    folds: List[Fold] = []
    inizio, idx = 0, 0
    while inizio + barre_train + barre_test <= n_comune:
        tr_da, tr_a = inizio, inizio + barre_train
        te_da, te_a = tr_a, tr_a + barre_test
        # ottimizzazione sul TRAIN aggregato
        migliore, miglior_p = None, -1e18
        for p in griglia:
            tot, ok = 0.0, True
            for s in simboli:
                r = fn(dati[s][tr_da:tr_a], p, capitale, fee, slippage_k)
                if r.trade < 2:
                    ok = False
                    break
                tot += r.ritorno
            if not ok:
                continue
            punteggio = tot / len(simboli)
            if punteggio > miglior_p:
                migliore, miglior_p = p, punteggio
        if migliore is None:
            inizio += barre_test
            continue
        # valutazione OUT-OF-SAMPLE aggregata
        test_ret, test_bh, test_bench = [], [], []
        for s in simboli:
            r = fn(dati[s][te_da:te_a], migliore, capitale, fee, slippage_k)
            test_ret.append(r.ritorno)
            c = dati[s]
            bh_s = c[te_a - 1]["c"] / c[te_da]["c"] - 1.0 if c[te_da]["c"] > 0 else 0.0
            test_bh.append(bh_s)
            # benchmark corretto: la strategia guadagna bh_s solo per la
            # frazione di tempo in cui e' effettivamente esposta
            test_bench.append((r.esposizione_pct / 100.0) * bh_s)
        folds.append(Fold(indice=idx, train_da=tr_da, train_a=tr_a,
                          test_da=te_da, test_a=te_a,
                          ritorno_train=miglior_p,
                          ritorno_test=sum(test_ret) / len(test_ret),
                          dd_test=0.0, trade_test=0,
                          bh_test=sum(test_bh) / len(test_bh),
                          bench_risk=sum(test_bench) / len(test_bench)))
        idx += 1
        inizio += barre_test
    if not folds:
        return [], {}, "nessun fold producibile"
    return folds, {}, ""


# ── momentum cross-sezionale (portafoglio) ─────────────────────────────────

def backtest_xsec(serie: Dict[str, List[dict]], p: Dict, capitale: float = 100.0,
                  fee: float = 0.002, slippage_k: float = 0.02) -> Risultato:
    """Momentum CROSS-SEZIONALE: non "questo sale?", ma "quale sale piu' degli altri?".

    Ogni N barre (parametro rebalance) si rankano gli asset per rendimento
    passato su M barre (parametro lookback) e si tiene equal-weight il paniere
    dei primi k; il resto a cash. E' una scommessa RELATIVA, non direzionale:
    se tutto scende, si sceglie chi scende meno.

    Perche' e' adatto a questo conto, a differenza di grid e trend:
    - il ribilanciamento e' raro (settimanale), quindi il turnover e' basso e
      le fee (0.20% per lato) non mangiano il premio. Il grid pagava il 25-65%
      del lordo in commissioni; qui il costo e' proporzionale al turnover.
    - il filtro di mercato opzionale (cash_filter_ma) manda tutto a cash
      quando il paniere equal-weight e' sotto la sua media: in un mercato orso
      non si resta long per forza.

    Costi: a ogni ribilanciamento si paga fee x turnover, dove turnover e' la
    somma dei valori assoluti delle variazioni di peso: vendere 0.2 e comprare
    0.2 costa 0.4 x fee.
    """
    simboli = sorted(serie)
    if len(simboli) < 3:
        return Risultato(nome="xsec", capitale=capitale, errore="meno di 3 simboli")
    n = min(len(serie[s]) for s in simboli)
    lookback = int(p.get("lookback", 180))
    k = int(p.get("k", 5))
    rebalance = int(p.get("rebalance", 42))
    filtro_ma = int(p.get("cash_filter_ma", 0))
    inizio = max(lookback, filtro_ma) + 1
    if n <= inizio + 10:
        return Risultato(nome="xsec", capitale=capitale, errore="serie troppo corta")

    prezzi = {s: [c["c"] for c in serie[s][-n:]] for s in simboli}
    ts = [c["ts"] for c in serie[simboli[0]][-n:]]

    equity = capitale
    pesi = {s: 0.0 for s in simboli}
    r = Risultato(nome="xsec", capitale=capitale)
    picco = capitale
    periodo = capitale

    for i in range(inizio, n):
        if i > inizio:
            ret = sum(pesi[s] * (prezzi[s][i] / prezzi[s][i - 1] - 1.0)
                      for s in simboli if prezzi[s][i - 1] > 0)
            equity *= (1.0 + ret)
        if (i - inizio) % rebalance == 0:
            mom = {}
            for s in simboli:
                p0 = prezzi[s][i - lookback]
                if p0 > 0:
                    mom[s] = prezzi[s][i] / p0 - 1.0
            nuovo = {s: 0.0 for s in simboli}
            if mom:
                vai_cash = False
                if filtro_ma:
                    if i >= filtro_ma:
                        media = sum(sum(prezzi[x][i - filtro_ma:i]) / filtro_ma
                                    for x in simboli) / len(simboli)
                        paniere = sum(prezzi[x][i] for x in simboli) / len(simboli)
                        vai_cash = paniere < media
                    else:
                        vai_cash = True
                if not vai_cash:
                    top = sorted(mom, key=lambda s: -mom[s])[:k]
                    for s in top:
                        nuovo[s] = 1.0 / len(top)
            turnover = sum(abs(nuovo[s] - pesi[s]) for s in simboli)
            equity *= (1.0 - fee * turnover)
            if turnover > 1e-9:
                r.trade_pnls.append(equity - periodo)
                periodo = equity
            pesi = nuovo
        if any(w > 1e-9 for w in pesi.values()):
            r.esposizione_bar += 1
        r.equity.append(equity)
        r.ts.append(ts[i])
        if equity > picco:
            picco = equity

    r.barre = len(r.equity)
    r.fee_pagate = 0.0
    r.lordo = sum(r.trade_pnls)
    return r


def walk_forward_xsec(serie: Dict[str, List[dict]], griglia: List[Dict],
                      capitale: float = 100.0, fee: float = 0.002,
                      barre_train: int = 1000, barre_test: int = 500,
                      slippage_k: float = 0.02) -> Tuple[List["Fold"], Dict, str]:
    """Walk-forward per il cross-sezionale: un set di parametri per tutti gli asset."""
    simboli = sorted(serie)
    n = min(len(serie[s]) for s in simboli)
    if n < barre_train + barre_test + 50:
        return [], {}, ("dati comuni insufficienti: il simbolo piu' corto ha "
                        "%d barre, servono %d" % (n, barre_train + barre_test + 50))
    dati = {s: serie[s][-n:] for s in simboli}
    folds: List[Fold] = []
    inizio, idx = 0, 0
    while inizio + barre_train + barre_test <= n:
        tr_da, tr_a = inizio, inizio + barre_train
        te_da, te_a = tr_a, tr_a + barre_test
        migliore, miglior_p = None, -1e18
        for p in griglia:
            rr = backtest_xsec({s: dati[s][tr_da:tr_a] for s in simboli}, p,
                               capitale, fee, slippage_k)
            if rr.errore or rr.trade < 2:
                continue
            punteggio = rr.ritorno - rr.max_dd
            if punteggio > miglior_p:
                migliore, miglior_p = p, punteggio
        if migliore is None:
            inizio += barre_test
            continue
        te = backtest_xsec({s: dati[s][te_da:te_a] for s in simboli}, migliore,
                           capitale, fee, slippage_k)
        bhs = []
        for s in simboli:
            c = dati[s]
            bhs.append(c[te_a - 1]["c"] / c[te_da]["c"] - 1.0 if c[te_da]["c"] > 0 else 0.0)
        bh = sum(bhs) / len(bhs)
        folds.append(Fold(indice=idx, train_da=tr_da, train_a=tr_a,
                          test_da=te_da, test_a=te_a,
                          ritorno_train=miglior_p, ritorno_test=te.ritorno,
                          dd_test=te.max_dd, trade_test=te.trade,
                          bh_test=bh, bench_risk=(te.esposizione_pct / 100.0) * bh))
        idx += 1
        inizio += barre_test
    if not folds:
        return [], {}, "nessun fold producibile"
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
    def ritorno_oos_composto(self) -> float:
        """Rendimento COMPOSTO dei periodi out-of-sample (cosa sarebbe successo)."""
        v = 1.0
        for f in self.fold:
            v *= (1.0 + f.ritorno_test)
        return v - 1.0

    @property
    def bh_oos_composto(self) -> float:
        """Buy-and-hold composto sugli STESSI periodi di test."""
        v = 1.0
        for f in self.fold:
            v *= (1.0 + f.bh_test)
        return v - 1.0

    @property
    def alpha_oos_composto(self) -> float:
        return self.ritorno_oos_composto - self.bh_oos_composto

    @property
    def peggior_fold(self) -> float:
        return min((f.ritorno_test for f in self.fold), default=0.0)

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
        # Tre condizioni, tutte fuori campione: i fold positivi in maggioranza,
        # il rendimento COMPOSTO positivo (cosa sarebbe successo davvero) e
        # l'alpha composto positivo (battere il semplice buy-and-hold).
        return (len(self.fold) >= 3 and self.fold_positivi >= 0.75
                and self.mediana_oos > 0 and self.trade_oos >= 30
                and self.ritorno_oos_composto > 0
                and self.alpha_oos_composto > 0)

    def riga(self) -> str:
        return ("%-9s %-5s fold=%2d pos=%3.0f%% medOOS=%+6.2f%% compOOS=%+8.2f%% "
                "alphaComp=%+8.2f%% pegg=%+6.2f%% trOOS=%4d | intero ret=%+7.2f%% "
                "dd=%5.1f%% sh=%5.2f tr=%4d feeL=%5.1f%% %s"
                % (self.simbolo, self.motore, len(self.fold),
                   100 * self.fold_positivi, 100 * self.mediana_oos,
                   100 * self.ritorno_oos_composto, 100 * self.alpha_oos_composto,
                   100 * self.peggior_fold, self.trade_oos, 100 * self.ritorno_intero,
                   100 * self.dd_intero, self.sharpe_intero, self.trade_intero,
                   self.fee_su_lordo,
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
