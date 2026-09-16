#!/usr/bin/env python3
"""Denaro — runner di backtest: replica il ciclo LIVE di BotTask.tick.

PERCHE' QUESTO FILE ESISTE
--------------------------
Il progetto decideva parametri con script ad-hoc mai versionati. Qui il ciclo
di trading e' la **stessa sequenza di operazioni** di
"denaro/application/orchestrator.py::BotTask.tick":

    equity → guardia equity → peak/drawdown → stop-loss → circuit breaker
    → balance/free → ordini aperti → prezzo → policy.decide()
    → preflight anti-deadlock → cancel → place → process fills → health

Le policy sono quelle REALI: vengono costruite da
"denaro.denaro_node.build_policy" (stessa factory della produzione), cosi'
il backtest non puo' divergere dal live per costruzione.
Il PortfolioManager e il RiskManager sono importati dal progetto.

DIFFERENZE DICHIARATE rispetto al live (approccio conservativo):
1. il prezzo di tick e' il **close della barra** (live: ticker ogni 30s);
2. un ordine creato durante una barra non puo' riempirsi nella stessa barra
   (nessun round-trip intrabar regalato);
3. il fill avviene **al prezzo limite**, senza miglioramento di prezzo;
4. nessun partial fill, nessuna latenza, nessun outage di exchange.

La curva di equity e' **mark-to-market** (cash + inventario × prezzo): e' la
metrica che il sistema live non ha mai misurato.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..application.portfolio import PortfolioManager
from ..domain.risk import RiskManager
from ..domain.types import CoreState
from .sim import SimExchange, SimFill, SimRejection

log = logging.getLogger("denaro.backtest")


# --- posizione (mark-to-market) ---------------------------------------------

class PositionTracker:
    """Costo medio dell'inventario, PnL realizzato e non realizzato.

    Invariante verificata nei test:
        equity - equity_iniziale == realized + unrealized
    """

    def __init__(self, qty: float = 0.0, cost: float = 0.0) -> None:
        self.qty = float(qty)
        self.cost = float(cost)
        self.realized = 0.0
        self.fees = 0.0

    def seed(self, qty: float, price: float) -> None:
        self.qty = float(qty)
        self.cost = float(qty) * float(price)

    def buy(self, amount: float, price: float, fee: float) -> None:
        self.qty += amount
        self.cost += amount * price + fee
        self.fees += fee

    def sell(self, amount: float, price: float, fee: float) -> float:
        amount = min(amount, self.qty)
        avg = (self.cost / self.qty) if self.qty > 1e-15 else price
        proceeds = amount * price - fee
        realized = proceeds - amount * avg
        self.realized += realized
        self.qty -= amount
        self.cost -= amount * avg
        self.fees += fee
        if self.qty < 1e-15:
            self.qty = 0.0
            self.cost = 0.0
        return realized

    def unrealized(self, price: float) -> float:
        return self.qty * price - self.cost


# --- configurazione ----------------------------------------------------------

@dataclass
class BacktestConfig:
    symbol: str
    capital: float
    bot: Dict[str, Any] = field(default_factory=dict)   # dict in stile node.yaml
    cash: float = 0.0                # liquidita' reale del conto (0 = usa capital)
    fee: float = 0.001
    min_amount: float = 0.0
    min_notional: float = 0.0
    amount_precision: float = 1e-8
    price_precision: float = 1e-8
    initial_asset: float = 0.0       # asset gia' in mano all'inizio (es. Kraken SOL)
    slippage: float = 0.0005
    stop_loss_pct: float = 0.0
    daily_loss_limit: float = 0.05
    max_drawdown_limit: float = 0.15
    weekly_loss_limit: float = 0.20
    max_consecutive_losses: int = 4
    guard_equity: bool = True        # replica _guard_equity del live

    def bot_dict(self) -> Dict[str, Any]:
        b = dict(self.bot or {})
        b.setdefault("symbol", self.symbol)
        b.setdefault("capital", self.capital)
        b.setdefault("fee", self.fee)
        b.setdefault("stop_loss_pct", self.stop_loss_pct)
        b.setdefault("daily_loss_limit", self.daily_loss_limit)
        b.setdefault("max_drawdown_limit", self.max_drawdown_limit)
        b.setdefault("weekly_loss_limit", self.weekly_loss_limit)
        return b


@dataclass
class BacktestResult:
    symbol: str
    bars: int
    start_ts: float
    end_ts: float
    start_price: float
    end_price: float
    start_equity: float
    end_equity: float
    initial_asset: float
    capital: float
    equity_curve: List[float] = field(default_factory=list)
    ts_curve: List[float] = field(default_factory=list)
    price_curve: List[float] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    fees_paid: float = 0.0
    cycles: int = 0
    cycle_wins: int = 0
    cycle_losses: int = 0
    orders_placed: int = 0
    orders_rejected: int = 0
    orders_canceled: int = 0
    fills_buy: int = 0
    fills_sell: int = 0
    blocked_ticks: int = 0
    blocked_reason: str = ""
    stop_loss_ts: Optional[float] = None
    equity_guard_hits: int = 0
    inventory_end: float = 0.0
    inventory_notional_max: float = 0.0
    avg_inventory_notional: float = 0.0
    trades: List[dict] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)
    final_basis: float = 0.0

    @property
    def inventory_cost_end(self) -> float:
        return self.final_basis


# --- runner ------------------------------------------------------------------

def run_backtest(cfg: BacktestConfig, bars: Sequence[Sequence[float]],
                 policy_factory=None, verbose: bool = False) -> BacktestResult:
    """Esegue il ciclo live bar-by-bar sui dati storici."""
    if not bars:
        raise ValueError("nessuna barra: dati vuoti")

    from ..denaro_node import build_policy  # import locale: evita cicli

    bot = cfg.bot_dict()
    sim = SimExchange(
        symbol=cfg.symbol, cash=(cfg.cash or cfg.capital), asset=cfg.initial_asset,
        fee=cfg.fee, min_amount=cfg.min_amount, min_notional=cfg.min_notional,
        amount_precision=cfg.amount_precision, price_precision=cfg.price_precision,
        slippage=cfg.slippage)
    policy = (policy_factory or build_policy)(bot, sim)
    risk = RiskManager(daily_loss_limit=cfg.daily_loss_limit,
                       max_drawdown_limit=cfg.max_drawdown_limit,
                       weekly_loss_limit=cfg.weekly_loss_limit,
                       max_consecutive_losses=cfg.max_consecutive_losses)
    risk_state = CoreState(initial_capital=cfg.capital,
                           current_capital=cfg.capital,
                           peak_capital=cfg.capital,
                           day_start_capital=cfg.capital,
                           week_start_capital=cfg.capital)
    portfolio = PortfolioManager(quote=sim.quote)

    # posizione seedata al primo prezzo disponibile (l'asset iniziale e' un
    # costo sostenuto PRIMA del backtest: il suo MTM misura il rendimento)
    pos = PositionTracker()
    p0 = float(bars[0][1])
    pos.seed(cfg.initial_asset, p0)

    res = BacktestResult(
        symbol=cfg.symbol, bars=len(bars),
        start_ts=float(bars[0][0]) / 1000.0, end_ts=float(bars[-1][0]) / 1000.0,
        start_price=p0, end_price=float(bars[-1][4]),
        start_equity=sim.equity(p0), end_equity=0.0,
        initial_asset=cfg.initial_asset, capital=cfg.capital)

    open_buys: Dict[str, dict] = {}
    open_sells: Dict[str, dict] = {}
    trading_paused = False
    stop_loss_triggered = False
    pending: List[SimFill] = []
    last_sane_equity = cfg.capital
    peak = res.start_equity
    inv_notional_sum = 0.0
    inv_notional_n = 0

    def process_fills(price: float, ts: float) -> None:
        """Replica di BotTask._process_fills: buy fill → piazza il TP sell."""
        while pending:
            f = pending.pop(0)
            if f.side == "buy":
                pos.buy(f.amount, f.price, f.fee)
                res.fills_buy += 1
                res.trades.append({"ts": ts, "event": "buy_filled", "amount": f.amount,
                                   "price": f.price, "fee": f.fee, "kind": f.kind})
                entry = f.price
                target = policy.sell_target(entry)
                try:
                    o = sim.create_limit_order(cfg.symbol, "sell", f.amount, target,
                                               kind="tp")
                    open_sells[o["id"]] = {"amount": f.amount, "entry_price": entry,
                                           "target_price": target, "timestamp": ts}
                except SimRejection as e:
                    res.rejections.append(f"tp sell: {e}")
            else:
                realized = pos.sell(f.amount, f.price, f.fee)
                res.fills_sell += 1
                res.cycles += 1
                if realized >= 0:
                    res.cycle_wins += 1
                else:
                    res.cycle_losses += 1
                res.trades.append({"ts": ts, "event": "sell_filled", "amount": f.amount,
                                   "price": f.price, "fee": f.fee,
                                   "realized": realized, "kind": f.kind})
                # P5: metriche di performance come nel live
                try:
                    risk_state.trade_results.append(realized)
                    risk_state.perf.update(realized / max(1e-9, cfg.capital))
                    risk_state.perf.recalc_ratios(
                        risk_state.trade_results, risk_state.peak_capital,
                        risk_state.current_capital, risk_state.initial_capital)
                except Exception:  # noqa: BLE001
                    pass

    for bar in bars:
        ts = float(bar[0]) / 1000.0
        price = float(bar[4])
        # 0) i fill avvengono meccanicamente nella barra (il bot li scopre al tick)
        pending.extend(sim.advance_bar(bar, ts))

        # 1) equity mark-to-market + guardia (replica _guard_equity del live).
        # C7: se l'equity e' fuori range il live SALTA il tick — non sostituisce
        # il valore, non aggiorna peak/drawdown e non decide. Il backtest deve
        # fare lo stesso, altrimenti misura una strategia che non esiste.
        equity = sim.equity(price)
        if cfg.guard_equity:
            lo, hi = cfg.capital * 0.05, cfg.capital * 30.0
            if equity <= lo or equity > hi:
                res.equity_guard_hits += 1
                continue
            last_sane_equity = equity

        # 2) peak / drawdown
        if equity > peak:
            peak = equity
        dd = (peak - equity) / max(1e-10, peak)

        # 3) stop-loss per bot (priorita': chiude, non solo blocca)
        if (cfg.stop_loss_pct > 0 and not stop_loss_triggered
                and dd > cfg.stop_loss_pct):
            stop_loss_triggered = True
            res.stop_loss_ts = ts
            trading_paused = True
            sim.cancel_all(cfg.symbol)
            open_buys.clear()
            open_sells.clear()
            if sim.asset > 0:
                try:
                    sim.sell_market(cfg.symbol, sim.asset)
                except SimRejection as e:
                    res.rejections.append(f"stop_loss: {e}")
            pending.clear()
            res.trades.append({"ts": ts, "event": "stop_loss", "drawdown": dd,
                               "equity": equity})
            res.equity_curve.append(sim.equity(price))
            res.ts_curve.append(ts)
            res.price_curve.append(price)
            continue

        # 4) circuit breaker (stato persistente come nel live)
        blocked = risk.check_circuit_breaker(risk_state, equity, ts)
        if blocked:
            res.blocked_ticks += 1
            res.blocked_reason = risk_state.cb.reason
            # MIRROR del live: il tick esce PRIMA di processare i fill
            res.equity_curve.append(equity)
            res.ts_curve.append(ts)
            res.price_curve.append(price)
            continue

        # 5) balance e ordini aperti (free vs locked)
        free = sim.free_quote()
        orders = sim.fetch_open_orders(cfg.symbol)
        portfolio.update(free, orders)

        # 6) policy: aggiorna lo storico e decide
        on_price = getattr(policy, "on_price", None)
        if on_price is not None:
            try:
                on_price(price)
            except Exception:  # noqa: BLE001
                pass
        free_asset = sim.free_base()
        risk_capital = risk.risk_sized_capital(risk_state, cfg.capital)

        try:
            decision = policy.decide(price, open_buys, open_sells, free,
                                     risk_capital, free, ts, free_asset=free_asset)
        except TypeError:
            decision = policy.decide(price, open_buys, open_sells, free,
                                     risk_capital, free, ts)

        # 6b) SafeMode / stop-loss: nessun NUOVO trade (i fill restano gestiti)
        if trading_paused:
            decision.to_place = []
            decision.to_sell = []
            decision.reason = "safemode: trading paused"

        # 7) grid bilaterale: i sell ladder non richiedono quote
        for amount, sell_price in getattr(decision, "to_sell", []):
            try:
                o = sim.create_limit_order(cfg.symbol, "sell", amount, sell_price,
                                           kind="ladder")
                # usa i valori ARROTONDATI dall'exchange (tick size reale)
                open_sells[o["id"]] = {"amount": o["amount"], "entry_price": price,
                                       "target_price": o["price"], "timestamp": ts}
            except SimRejection as e:
                res.rejections.append(f"ladder sell: {e}")

        # 7b) fill processing PRE-preflight (come il live: orchestrator.py:341 —
        #     un buy fillato deve diventare un TP sell anche se il preflight
        #     blocca i nuovi buy, altrimenti l'inventario resta appeso)
        process_fills(price, ts)

        # 8) preflight anti-deadlock (stesso PortfolioManager del live)
        min_notional = cfg.min_notional
        per_level = risk_capital / max(1, int(bot.get("levels", 3)))
        if getattr(decision, "to_place", None) or min_notional > 0:
            ok, reason, speculative = portfolio.preflight(
                cfg.symbol, min_notional, per_level, price, free)
            if not ok:
                for oid in speculative:
                    try:
                        sim.cancel_order(oid, cfg.symbol)
                        open_buys.pop(oid, None)
                    except SimRejection:
                        pass
                res.equity_curve.append(equity)
                res.ts_curve.append(ts)
                res.price_curve.append(price)
                continue

        to_place = [l for l in getattr(decision, "to_place", [])
                    if min_notional <= 0 or l.notional >= min_notional]

        # 9) esecuzione: cancel poi place
        for oid in getattr(decision, "to_cancel", []):
            try:
                sim.cancel_order(oid, cfg.symbol)
                open_buys.pop(oid, None)
            except SimRejection:
                open_buys.pop(oid, None)
        for level in to_place:
            try:
                o = sim.create_limit_order(cfg.symbol, "buy", level.amount,
                                           level.buy_price, kind="grid")
                # usa i valori ARROTONDATI dall'exchange (tick size reale)
                open_buys[o["id"]] = {"amount": o["amount"], "price": o["price"],
                                      "timestamp": ts, "level": level.level}
            except SimRejection as e:
                res.rejections.append(f"buy: {e}")
                res.orders_rejected += 1

        # 10) fill processing post-place (come il live)
        process_fills(price, ts)

        # metriche di stato
        inv_notional = sim.asset * price
        inv_notional_sum += inv_notional
        inv_notional_n += 1
        res.inventory_notional_max = max(res.inventory_notional_max, inv_notional)
        res.equity_curve.append(sim.equity(price))
        res.ts_curve.append(ts)
        res.price_curve.append(price)

    process_fills(sim.price, float(bars[-1][0]) / 1000.0)
    res.end_equity = sim.equity(sim.price)
    res.realized_pnl = pos.realized
    res.unrealized_pnl = pos.unrealized(sim.price)
    res.fees_paid = pos.fees
    res.inventory_end = sim.asset
    res.final_basis = pos.cost
    res.orders_placed = sim.stats["placed"]
    res.orders_canceled = sim.stats["canceled"]
    res.avg_inventory_notional = (inv_notional_sum / inv_notional_n
                                  if inv_notional_n else 0.0)
    return res
