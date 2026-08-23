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
    state_path: Optional[Path] = None
    journal_path: Optional[Path] = None
    health_path: Optional[Path] = None


# --- bot task ----------------------------------------------------------------

class BotTask:
    """Worker asincrono di un singolo bot grid."""

    def __init__(self, config: BotConfig, exchange: ExchangePort,
                 policy: GridPolicy, risk: RiskManager,
                 get_equity: Optional[callable] = None,
                 now: Optional[callable] = None) -> None:
        self.cfg = config
        self.ex = exchange
        self.policy = policy
        self.risk = risk
        self._get_equity = get_equity or self._default_equity
        self._now = now or time.time
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_error: str = ""

        self.state = BotState(symbol=config.symbol, start_ts=self._now())
        self.store = StateStore(Path(config.state_path)) if config.state_path else None
        self.journal = Journal(Path(config.journal_path)) if config.journal_path else None
        self.health = AtomicFile(Path(config.health_path)) if config.health_path else None

        # stato di rischio PERSISTENTE tra i tick (peak/drawdown/daily tracking)
        self.risk_state = CoreState(initial_capital=config.capital,
                                    current_capital=config.capital,
                                    peak_capital=config.capital,
                                    day_start_capital=config.capital)

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
        equity = self._get_equity()
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        dd = (self.state.peak_equity - equity) / max(1e-10, self.state.peak_equity)
        self.state.max_dd = max(self.state.max_dd, dd)

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
        try:
            t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
            price = float(t["last"])
        except Exception as e:  # noqa: BLE001
            self._last_error = f"ticker: {e}"
            self._write_health(equity, blocked=False)
            return

        # 3) decisione (policy pura — idempotente)
        decision = self.policy.decide(price, self.state.open_buys,
                                      self.state.open_sells, free,
                                      self.cfg.capital, free, now)

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
        self._write_health(equity, blocked=False)
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
                profit = float(info["amount"]) * (float(info["target_price"]) - float(info["entry_price"]))
                self.state.total_pnl += profit
                self.state.total_trades += 1
                if profit >= 0:
                    self.state.wins += 1
                else:
                    self.state.losses += 1
                self.state.volume += float(info["amount"]) * float(info["target_price"])
                self._journal("sell_filled", order_id=oid,
                              amount=float(info["amount"]),
                              entry=float(info["entry_price"]),
                              exit=float(info["target_price"]),
                              profit=profit, total_pnl=self.state.total_pnl)
                self.state.open_sells.pop(oid, None)
            elif st in ("canceled", "expired", "rejected"):
                self.state.open_sells.pop(oid, None)

    # --- health --------------------------------------------------------------

    def _write_health(self, equity: float, blocked: bool) -> None:
        if self.health is None:
            return
        payload = {
            "symbol": self.cfg.symbol,
            "status": "blocked" if blocked else "running",
            "capital": self.cfg.capital,
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
    """Gestisce il ciclo di vita di N BotTask (1 processo asyncio per nodo)."""

    def __init__(self, supervisor=None) -> None:
        self._bots: Dict[str, BotTask] = {}
        self._supervisor = supervisor

    def add_bot(self, bot: BotTask) -> None:
        if bot.cfg.symbol in self._bots:
            raise ValueError(f"bot gia' registrato: {bot.cfg.symbol}")
        self._bots[bot.cfg.symbol] = bot

    async def start_all(self) -> None:
        for symbol, bot in self._bots.items():
            if self._supervisor and not self._supervisor.can_start_worker():
                log.warning("supervisor: worker %s non avviato (risorse)", symbol)
                continue
            bot._task = asyncio.create_task(bot.run())
            log.info("bot %s avviato", symbol)

    async def stop_all(self) -> None:
        for bot in self._bots.values():
            await bot.stop()

    @property
    def bots(self) -> Dict[str, BotTask]:
        return self._bots
