#!/usr/bin/env python3
"""Denaro — TradeOrchestrator e BotTask (M4/D1 del blueprint).

`BotTask` e' il worker leggero di un bot: un task asyncio che combina
- `GridPolicy` (domain, re-grid idempotente — fix C7)
- `RiskManager` (domain, circuit breaker azionato)
- `ExchangePort` (infrastructure: OKXAdapter/KrakenAdapter o fake nei test)
- `Journal` + `StateStore` (infrastructure: persistenza robusta)
- `MarketDataHub` (infrastructure: prezzo condiviso)

Il ciclo `tick()` e' deterministico e testabile con un FakeExchange.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..domain.grid import GridDecision, GridLevel, GridPolicy
from ..domain.risk import RiskManager
from ..domain.types import CBState, CoreState
from ..infrastructure.storage import AtomicFile, Journal, StateStore
from .portfolio import PortfolioManager

log = logging.getLogger("denaro.bot")


# --- porta exchange ----------------------------------------------------------

class ExchangePort:
    """Contratto minimo di un exchange (REST). OKXAdapter lo rispetta."""

    def fetch_ticker(self, symbol: str) -> dict: ...            # pragma: no cover
    def fetch_balance(self) -> dict: ...                        # pragma: no cover
    def fetch_open_orders(self, symbol: str) -> List[dict]: ...  # pragma: no cover
    def fetch_order(self, order_id: str, symbol: str) -> dict: ...  # pragma: no cover
    def create_limit_order(self, symbol: str, side: str, amount: float,
                           price: float) -> dict: ...           # pragma: no cover
    def cancel_order(self, order_id: str, symbol: str) -> dict: ...  # pragma: no cover
    def sell_market(self, symbol: str, amount: float) -> dict: ...  # pragma: no cover


# --- stato bot ---------------------------------------------------------------

@dataclass
class BotState:
    symbol: str = ""
    open_buys: Dict[str, dict] = field(default_factory=dict)
    open_sells: Dict[str, dict] = field(default_factory=dict)
    total_pnl: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    volume: float = 0.0
    peak_equity: float = 0.0
    max_dd: float = 0.0
    start_ts: float = 0.0
    stop_loss_triggered: bool = False   # persistente: stop-loss gia' eseguito

    @property
    def open_count(self) -> int:
        return len(self.open_buys)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "BotState":
        return cls(**{k: d.get(k, v) for k, v in cls().__dict__.items() if k != "symbol"})


@dataclass
class BotConfig:
    symbol: str
    capital: float
    levels: int = 3
    buy_distance: float = 0.01
    profit_target: float = 0.015
    tick_interval: float = 60.0
    fee: float = 0.0                # fee per lato (frazione); 0 = accounting v3.3
    bot_key: str = ""               # id univoco (mode:env_prefix:symbol)
    state_path: Optional[Path] = None
    journal_path: Optional[Path] = None
    health_path: Optional[Path] = None
    stop_loss_pct: float = 0.0      # drawdown dal peak → chiudi posizioni e ferma
    max_slippage: float = 0.005     # P2: spread max tollerato per market order


# --- bot task ----------------------------------------------------------------

class BotTask:
    """Worker asincrono di un singolo bot grid."""

    def __init__(self, config: BotConfig, exchange: ExchangePort,
                 policy: GridPolicy, risk: RiskManager,
                 get_equity: Optional[callable] = None,
                 now: Optional[callable] = None,
                 price_source: Optional[callable] = None) -> None:
        self.cfg = config
        self.ex = exchange
        self.policy = policy
        self.risk = risk
        self._get_equity = get_equity or self._default_equity
        self._now = now or time.time
        # fonte del prezzo: hub condiviso (M6+) oppure fetch_ticker dell'exchange
        self._price_source = price_source
        # SafeMode: flag impostato dal ResourceGuardian (TODO punto 3)
        self.trading_paused = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_error: str = ""
        # stop-loss gia' scattato (persistente: non rivende dopo un restart)
        self._stop_loss_triggered = False
        # portfolio manager anti-deadlock (capitale virtuale + preflight dedup)
        self.portfolio = PortfolioManager(quote=self.cfg.symbol.split("/")[-1])

        self.state = BotState(symbol=config.symbol, start_ts=self._now())
        self.store = StateStore(Path(config.state_path)) if config.state_path else None
        self.journal = Journal(Path(config.journal_path)) if config.journal_path else None
        self.health = AtomicFile(Path(config.health_path)) if config.health_path else None

        # stato di rischio PERSISTENTE tra i tick (peak/drawdown/daily/weekly)
        # NB: week_start_capital DEVE essere capital, non il default 100.0 della
        # dataclass — altrimenti il max() della baseline settimanale resta
        # avvelenato a 100 → weekly_loss_-99% spurio (bug visto in produzione).
        self.risk_state = CoreState(initial_capital=config.capital,
                                    current_capital=config.capital,
                                    peak_capital=config.capital,
                                    day_start_capital=config.capital,
                                    week_start_capital=config.capital)

        self._load_state()
        self._rebuild_from_exchange()

    # --- persistence ---------------------------------------------------------

    def _load_state(self) -> None:
        if self.store is None:
            return
        data = self.store.load()
        if isinstance(data, dict) and data.get("symbol"):
            self.state = BotState.from_dict(data)

    def _save_state(self) -> None:
        if self.store is not None:
            self.store.save(self.state.to_dict())

    def _journal(self, event: str, **fields) -> None:
        if self.journal is None:  # attenzione: Journal ha __len__ → non usare `not`
            return
        record = {"event": event, "symbol": self.cfg.symbol, "ts": self._now(), **fields}
        self.journal.append(record)

    def _rebuild_from_exchange(self) -> None:
        """Ricostruisce lo stato dagli ordini aperti + journal (replay PnL)."""
        # 1) PnL/trades dalla storia (journal immutabile → totale ricostruito)
        if self.journal is not None:
            pnl = trades = wins = losses = 0.0
            for r in self.journal.read_all():
                if r.get("symbol") != self.cfg.symbol:
                    continue
                if r.get("event") == "sell_filled":
                    pnl += float(r.get("profit", 0))
                    trades += 1
                    wins += 1 if float(r.get("profit", 0)) >= 0 else 0
                    losses += 1 if float(r.get("profit", 0)) < 0 else 0
            self.state.total_pnl = pnl
            self.state.total_trades = int(trades)
            self.state.wins = int(wins)
            self.state.losses = int(losses)
        # 2) ordini aperti dall'exchange
        try:
            for o in self.ex.fetch_open_orders(self.cfg.symbol):
                oid, side = o["id"], o["side"]
                amount, price = float(o["amount"]), float(o["price"])
                if side == "buy":
                    self.state.open_buys[oid] = {
                        "amount": amount, "price": price,
                        "timestamp": self._now(), "level": 0}
                else:
                    self.state.open_sells[oid] = {
                        "amount": amount, "entry_price": price * 0.99,
                        "target_price": price, "timestamp": self._now()}
        except Exception as e:  # noqa: BLE001
            log.warning("rebuild open orders fallito: %s", e)

    # --- equity --------------------------------------------------------------

    def _default_equity(self) -> float:
        """Equity di default = capitale (senza porta equity dedicata)."""
        return self.cfg.capital

    # --- tick -----------------------------------------------------------------

    async def tick(self) -> None:
        """Un ciclo completo: risk → prezzo → decisione → esecuzione → health."""
        now = self._now()
        # equity reale: get_equity puo' fare I/O (fetch live) → to_thread
        equity = await asyncio.to_thread(self._get_equity)
        equity = self._guard_equity(equity)
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        dd = (self.state.peak_equity - equity) / max(1e-10, self.state.peak_equity)
        self.state.max_dd = max(self.state.max_dd, dd)

        # 0) STOP-LOSS per bot (PRIORITA' sul CB: chiude posizioni, non solo
        #    blocca i nuovi ordini). Drawdown dal peak oltre la soglia →
        #    cancella ordini + vendita asset + ferma. Persistente.
        if (self.cfg.stop_loss_pct > 0 and not self.state.stop_loss_triggered
                and dd > self.cfg.stop_loss_pct):
            await self._trigger_stop_loss(equity, dd, None)
            return

        # 1) risk check (circuit breaker AZIONATO — stato persistente tra i tick)
        blocked = self.risk.check_circuit_breaker(self.risk_state, equity, now)
        if blocked:
            self._last_error = f"CB OPEN: {self.risk_state.cb.reason}"
            self._write_health(equity, blocked=True)
            self._save_state()
            return

        # 2) prezzo (hub con cache, fallback fetch)
        try:
            bal = await asyncio.to_thread(self.ex.fetch_balance)
            free = float(bal.get("free", {}).get("EUR") or 0)
            total = float(bal.get("total", {}).get("EUR") or 0)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"balance: {e}"
            self._write_health(equity, blocked=False)
            return

        # aggiorna il portfolio con i dati gia' in mano (niente API extra)
        try:
            orders = await asyncio.to_thread(self.ex.fetch_open_orders, self.cfg.symbol)
            self.portfolio.update(free, orders)
        except Exception:  # noqa: BLE001 - il preflight usera' solo free
            self.portfolio.update(free, [])
        try:
            if self._price_source is not None:
                price = float(self._price_source())
            else:
                t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                price = float(t["last"])
        except Exception as e:  # noqa: BLE001
            self._last_error = f"ticker: {e}"
            self._write_health(equity, blocked=False)
            return

        # 3) decisione (policy pura — idempotente)
        #    aggiorna prima lo storico della strategia (momentum/meanrev)
        on_price = getattr(self.policy, "on_price", None)
        if on_price is not None:
            try:
                on_price(price)
            except Exception:  # noqa: BLE001
                pass
        # asset libero del base currency (per il grid bilaterale)
        base = self.cfg.symbol.split("/")[0]
        try:
            free_asset = float((bal.get("free", {}) or {}).get(base, 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            free_asset = 0.0
        # P2 — Volatility Targeting: capitale effettivo della griglia scalato
        # per regime (exposure_factor) e Kelly (kelly_scale). Neutro di default
        # (normal + kelly 0.25 → ×1.0); si contrae in high/extreme vol e con CB.
        risk_capital = self.risk.risk_sized_capital(self.risk_state, self.cfg.capital)
        try:
            decision = self.policy.decide(price, self.state.open_buys,
                                          self.state.open_sells, free,
                                          risk_capital, free, now,
                                          free_asset=free_asset)
        except TypeError:
            # policy legacy senza free_asset (momentum/meanrev/adaptive)
            decision = self.policy.decide(price, self.state.open_buys,
                                          self.state.open_sells, free,
                                          risk_capital, free, now)

        # 3a) SafeMode (TODO punto 3): nessun NUOVO trade se la RAM e' critica;
        #     le posizioni esistenti continuano a essere gestite (fill/exit)
        if self.trading_paused:
            decision.to_place = []
            decision.to_sell = []
            decision.reason = "safemode: trading paused"

        # 3aa) GRID BILATERALE: i SELL ladder NON richiedono EUR (usano l'asset
        #      in mano) → si eseguono SEMPRE, anche se il preflight blocca i
        #      buy per mancanza di free (es. ADA con 0 EUR e 9.8 ADA free).
        for amount, sell_price in decision.to_sell:
            try:
                o = await asyncio.to_thread(
                    self.ex.create_limit_order, self.cfg.symbol, "sell",
                    amount, sell_price)
                if o:
                    self.state.open_sells[o["id"]] = {
                        "amount": amount, "entry_price": price,
                        "target_price": sell_price, "timestamp": self._now()}
                    self._journal("sell_placed", order_id=o["id"],
                                  amount=amount, price=sell_price,
                                  kind="ladder")
            except Exception as e:  # noqa: BLE001
                self._last_error = f"place sell ladder: {e}"
        if decision.to_sell:
            log.info("grid bilaterale %s: %d sell ladder piazzati",
                     self.cfg.symbol, len(decision.to_sell))

        # 3b) PRE-FLIGHT anti-deadlock (ATLAS v6): fattibilita' BUY prima
        #     delle API. Capitale usabile = free + locked×0.85 (ordini buy
        #     cancellabili); dedup degli ordini speculari (buy sopra il mercato).
        min_notional = self._min_notional()
        per_level = risk_capital / max(1, self.cfg.levels)
        if decision.to_place or min_notional > 0:
            ok, reason, speculative = self.portfolio.preflight(
                self.cfg.symbol, min_notional, per_level, price, free)
            if not ok:
                self._last_error = f"PRE-FLIGHT BLOCK: {reason}"
                # cancella gli ordini speculari (capitale congelato) via API
                for oid in speculative:
                    try:
                        await asyncio.to_thread(self.ex.cancel_order,
                                                oid, self.cfg.symbol)
                        self.state.open_buys.pop(oid, None)
                        self._journal("buy_canceled", order_id=oid)
                    except Exception:  # noqa: BLE001
                        pass
                self._write_health(equity, blocked=False)
                self._save_state()
                return
        if decision.to_place:
            decision.to_place = [l for l in decision.to_place
                                 if min_notional <= 0 or l.notional >= min_notional]

        # 4) esecuzione
        for oid in decision.to_cancel:
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
                self.state.open_buys.pop(oid, None)
                self._journal("buy_canceled", order_id=oid)
            except Exception as e:  # noqa: BLE001
                self._last_error = f"cancel {oid}: {e}"
        for level in decision.to_place:
            try:
                o = await asyncio.to_thread(
                    self.ex.create_limit_order, self.cfg.symbol, "buy",
                    level.amount, level.buy_price)
                if o:
                    self.state.open_buys[o["id"]] = {
                        "amount": level.amount, "price": level.buy_price,
                        "timestamp": self._now(), "level": level.level}
                    self._journal("buy_placed", order_id=o["id"],
                                  amount=level.amount, price=level.buy_price,
                                  level=level.level)
            except Exception as e:  # noqa: BLE001
                self._last_error = f"place buy: {e}"

        # 5) fill processing
        await self._process_fills(price)

        self._last_error = ""
        self._write_health(equity, blocked=False, free_quote=free)
        self._save_state()

    def _guard_equity(self, equity: float) -> float:
        """P2 — sanity dell'equity: letture impossibili (spike/dip da fetch
        sporco) sostituite con l'ultimo valore valido. Range plausibile per
        conti micro: [5% , 30×] del capitale — evita che una lettura sporca
        avveleni peak/daily/weekly baseline (bug weekly_loss_-99% visto in
        produzione su DOGE nuvola)."""
        cap = max(1e-9, self.cfg.capital)
        lo, hi = cap * 0.05, cap * 30.0
        if equity is None or equity != equity or equity <= lo or equity > hi:
            prev = getattr(self, "_last_sane_equity", cap)
            log.warning("equity sospetta %.4f per %s → uso %.4f",
                        equity, self.cfg.symbol, prev)
            return prev
        self._last_sane_equity = equity
        return equity

    def _available_capital(self, free: float) -> float:
        """Equity dinamica anti-deadlock: free + locked×0.85 (ATLAS v6)."""
        # usa il portfolio manager (con i dati gia' caricati nel tick)
        try:
            return self.portfolio.total_available(free)
        except Exception:
            pass
        # fallback: metodo legacy dell'adapter (senza fattore di sconto)
        fn = getattr(self.ex, "available_trading_capital", None)
        if fn is None:
            return free
        try:
            quote = self.cfg.symbol.split("/")[1] if "/" in self.cfg.symbol else "EUR"
            return fn(quote)
        except Exception:
            return free

    def _min_notional(self) -> float:
        fn = getattr(self.ex, "min_notional", None)
        if fn is None:
            return 0.0
        try:
            return float(fn(self.cfg.symbol) or 0.0)
        except Exception:
            return 0.0

    async def _trigger_stop_loss(self, equity: float, drawdown: float,
                                 price: Optional[float]) -> None:
        """STOP-LOSS: cancella tutti gli ordini, vende tutto l'asset disponibile
        e ferma il bot. Flag persistente per non ripetere dopo un restart."""
        self.state.stop_loss_triggered = True
        self.trading_paused = True
        self._last_error = f"STOP LOSS: drawdown {drawdown * 100:.1f}%"
        log.warning("STOP LOSS %s: drawdown %.1f%% equity %.2f",
                    self.cfg.symbol, drawdown * 100, equity)

        # prezzo per la vendita: dal parametro oppure fetch one-shot
        if price is None:
            try:
                if self._price_source is not None:
                    price = float(self._price_source())
                else:
                    t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                    price = float(t["last"])
            except Exception:  # noqa: BLE001
                price = 0.0

        # 1) cancella ordini aperti (buy e sell)
        for oid in list(self.state.open_buys):
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                pass
        for oid in list(self.state.open_sells):
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                pass
        self.state.open_buys.clear()
        self.state.open_sells.clear()

        # 1b) P2 — SLIPPAGE TOLERANCE: prima di vendere al market, se lo spread
        #     bid/ask supera max_slippage si BLOCCA la vendita e si riprova al
        #     tick successivo (evita di svendere in mercati illiquidi/impazziti;
        #     flag resettato per non perdere lo stop-loss). Fail-open se lo
        #     spread non e' misurabile (meglio vendere che restare esposti).
        max_slip = getattr(self.cfg, "max_slippage", 0.0) or 0.0
        if max_slip > 0:
            try:
                t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                bid = float(t.get("bid") or 0.0)
                ask = float(t.get("ask") or 0.0)
                if bid > 0 and ask > 0:
                    mid = (bid + ask) / 2.0
                    spread = (ask - bid) / mid
                    if spread > max_slip:
                        self._last_error = (f"STOP LOSS BLOCCATO: spread "
                                            f"{spread * 100:.2f}% > max "
                                            f"{max_slip * 100:.2f}%")
                        self.state.stop_loss_triggered = False  # riprova
                        self._journal("stop_loss_blocked_slippage",
                                      spread=round(spread, 4),
                                      max_slippage=max_slip)
                        self._write_health(equity, blocked=True)
                        self._save_state()
                        return
            except Exception:  # noqa: BLE001
                pass  # fail-open: non misurabile → procedi

        # 2) vendi l'asset posseduto (free balance del base asset)
        base = self.cfg.symbol.split("/")[0]
        try:
            bal = await asyncio.to_thread(self.ex.fetch_balance)
            amount = float((bal.get("free", {}) or {}).get(base, 0.0) or 0.0)
            if amount > 0:
                await asyncio.to_thread(self.ex.sell_market, self.cfg.symbol, amount)
                self._journal("stop_loss_sell", amount=amount,
                              drawdown=round(drawdown, 4), price=price)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"stop loss sell: {e}"
            log.error("STOP LOSS %s: vendita fallita: %s", self.cfg.symbol, e)

        self._journal("stop_loss", drawdown=round(drawdown, 4), equity=equity)
        self._write_health(equity, blocked=True)
        self._save_state()

    async def _process_fills(self, price: float) -> None:
        """Controlla i buy aperti: su fill piazza il sell al TP e journal."""
        for oid, info in list(self.state.open_buys.items()):
            try:
                o = await asyncio.to_thread(self.ex.fetch_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                continue
            st = o.get("status", "open")
            if st in ("closed", "filled"):
                entry = float(info["price"])
                target = self.policy.sell_target(entry)
                try:
                    sell = await asyncio.to_thread(
                        self.ex.create_limit_order, self.cfg.symbol, "sell",
                        float(info["amount"]), target)
                    if sell:
                        self.state.open_sells[sell["id"]] = {
                            "amount": float(info["amount"]), "entry_price": entry,
                            "target_price": target, "timestamp": self._now()}
                        self._journal("buy_filled", order_id=oid, entry=entry,
                                      amount=float(info["amount"]),
                                      sell_target=target)
                except Exception as e:  # noqa: BLE001
                    self._last_error = f"place sell: {e}"
                self.state.open_buys.pop(oid, None)
            elif st in ("canceled", "expired", "rejected"):
                self.state.open_buys.pop(oid, None)

        for oid, info in list(self.state.open_sells.items()):
            try:
                o = await asyncio.to_thread(self.ex.fetch_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                continue
            st = o.get("status", "open")
            if st in ("closed", "filled"):
                # PnL fee-aware: proceeds×(1-fee) - cost×(1+fee). Con fee=0
                # il comportamento e' identico all'accounting del motore v3.3.
                amount = float(info["amount"])
                entry = float(info["entry_price"])
                target = float(info["target_price"])
                cost = amount * entry * (1 + self.cfg.fee)
                proceeds = amount * target * (1 - self.cfg.fee)
                profit = proceeds - cost
                self.state.total_pnl += profit
                self.state.total_trades += 1
                if profit >= 0:
                    self.state.wins += 1
                else:
                    self.state.losses += 1
                self.state.volume += amount * target
                self._journal("sell_filled", order_id=oid,
                              amount=float(info["amount"]),
                              entry=float(info["entry_price"]),
                              exit=float(info["target_price"]),
                              profit=profit, total_pnl=self.state.total_pnl)
                self.state.open_sells.pop(oid, None)
            elif st in ("canceled", "expired", "rejected"):
                self.state.open_sells.pop(oid, None)

    # --- health --------------------------------------------------------------

    def _write_health(self, equity: float, blocked: bool, free_quote: float = 0.0) -> None:
        if self.health is None:
            return
        payload = {
            "symbol": self.cfg.symbol,
            "status": "blocked" if blocked else "running",
            "capital": self.cfg.capital,
            "free_quote": round(free_quote, 4),
            "total_equity": round(equity, 4),
            "buys": len(self.state.open_buys),
            "sells": len(self.state.open_sells),
            "pnl": round(self.state.total_pnl, 6),
            "trades": self.state.total_trades,
            "wins": self.state.wins,
            "losses": self.state.losses,
            "volume": round(self.state.volume, 4),
            "drawdown": round(self.state.max_dd, 4),
            "uptime": round(self._now() - self.state.start_ts, 0),
            "error": self._last_error,
            "timestamp": self._now(),
        }
        # ATLAS v6: strategia + regime (se la policy e' adattiva) + risk info
        payload["strategy"] = self.policy.__class__.__name__.replace("Policy", "").lower()
        regime = getattr(self.policy, "regime", None)
        if regime is not None:
            try:
                payload["regime"] = regime.name
                payload["adx"] = round(float(regime.adx), 2)
                payload["atr_pct"] = round(float(regime.atr_pct) * 100, 3)
                payload["ema200"] = round(float(regime.ema200), 4)
                payload["rsi"] = round(float(regime.rsi), 1)
                payload["regime_confidence"] = round(float(regime.signal_confidence), 3)
                payload["hurst"] = round(float(getattr(regime, "hurst", 0.5)), 3)
            except Exception:  # noqa: BLE001
                pass
        payload["stop_loss_triggered"] = bool(self.state.stop_loss_triggered)
        try:
            payload["cap_locked"] = round(float(self.portfolio.locked), 4)
            payload["cap_available"] = round(float(self.portfolio.total_available()), 4)
        except Exception:  # noqa: BLE001
            pass
        self.health.write_json(payload)

    # --- run loop ------------------------------------------------------------

    async def run(self) -> None:
        self._running = True
        self.state.start_ts = self._now()
        while self._running:
            try:
                await self.tick()
            except Exception as e:  # noqa: BLE001 - il bot non deve morire
                self._last_error = f"tick: {e}"
                log.error("bot %s tick error: %s", self.cfg.symbol, e)
            await asyncio.sleep(self.cfg.tick_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class TradeOrchestrator:
    """Gestisce il ciclo di vita di N BotTask (1 processo asyncio per nodo).

    Identifica i bot per `bot_key` (mode:env_prefix:symbol) — lo stesso symbol
    puo' vivere su piu' account (paper + live OKX/Kraken).
    """

    OHLCV_TIMEFRAME = "1h"
    OHLCV_LIMIT = 200
    OHLCV_REFRESH_S = 60.0

    def __init__(self, supervisor=None) -> None:
        self._bots: Dict[str, BotTask] = {}
        self._supervisor = supervisor
        self._ohlcv_sources: Dict[str, tuple] = {}  # symbol -> (exchange, callback)
        self._ohlcv_tasks: Dict[str, asyncio.Task] = {}

    def add_bot(self, bot: BotTask) -> None:
        key = bot.cfg.bot_key or bot.cfg.symbol
        if key in self._bots:
            raise ValueError(f"bot gia' registrato: {key}")
        self._bots[key] = bot

    def add_ohlcv_source(self, symbol: str, exchange, callback) -> None:
        """Alimenta la policy adattiva con OHLCV reale (candle 1h, refresh 60s)."""
        self._ohlcv_sources[symbol] = (exchange, callback)

    async def _ohlcv_loop(self, symbol: str) -> None:
        exchange, callback = self._ohlcv_sources[symbol]
        # preferisce fetch_ohlcv_raw (bypassa il bug ccxt 4.5.x), fallback
        fetch = getattr(exchange, "fetch_ohlcv_raw", None) or getattr(
            exchange, "fetch_ohlcv", None)
        if fetch is None:
            log.warning("ohlcv %s: exchange senza fetch_ohlcv — canale disattivo",
                        symbol)
            return
        while True:
            try:
                ohlcv = await asyncio.to_thread(
                    fetch, symbol, self.OHLCV_TIMEFRAME, self.OHLCV_LIMIT)
                if ohlcv:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(symbol, ohlcv)
                    else:
                        callback(symbol, ohlcv)
            except Exception as e:  # noqa: BLE001 - il regime resta sul fallback prezzi
                log.warning("ohlcv %s fallito: %s", symbol, e)
            await asyncio.sleep(self.OHLCV_REFRESH_S)

    async def start_all(self) -> None:
        for symbol in list(self._ohlcv_sources):
            self._ohlcv_tasks[symbol] = asyncio.create_task(
                self._ohlcv_loop(symbol))
            log.info("ohlcv source %s avviato", symbol)
        for symbol, bot in self._bots.items():
            if self._supervisor and not self._supervisor.can_start_worker():
                log.warning("supervisor: worker %s non avviato (risorse)", symbol)
                continue
            bot._task = asyncio.create_task(bot.run())
            log.info("bot %s avviato", symbol)

    async def stop_all(self) -> None:
        for t in self._ohlcv_tasks.values():
            t.cancel()
        if self._ohlcv_tasks:
            await asyncio.gather(*self._ohlcv_tasks.values(),
                                 return_exceptions=True)
        self._ohlcv_tasks.clear()
        for bot in self._bots.values():
            await bot.stop()

    @property
    def bots(self) -> Dict[str, BotTask]:
        return self._bots
