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
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..domain.equity import EquityTracker
from ..domain.grid import GridDecision, GridLevel, GridPolicy
from ..domain.risk import RiskManager
from ..domain.types import CBState, CoreState
from ..infrastructure.exchanges.errors import PermanentExchangeError
from ..infrastructure.storage import AtomicFile, Journal, StateStore
from .portfolio import PortfolioManager

log = logging.getLogger("denaro.bot")


def _sell_parts(item) -> tuple:
    """Normalizza una voce di `GridDecision.to_sell`.

    Le policy storiche emettono 2-tuple `(amount, price)`; GridPolicy aggiunge
    il livello della scala come terzo elemento. Tollerare entrambe le arity
    evita di rompere momentum/meanrev/irmr/mincapture quando la griglia evolve.
    """
    amount, price = float(item[0]), float(item[1])
    level = int(item[2]) if len(item) > 2 else -1
    return amount, price, level


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
    # Posizione detenuta da una policy a STOP MONITORATO (trend): non esiste un
    # ordine di vendita a cui appoggiarsi, quindi entry/amount vivono qui.
    # Servono alla contabilita' del PnL e alla riconciliazione dopo un restart.
    posizione_aperta: Optional[dict] = None

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
    # stato di RISCHIO persistente (CoreState: peak/daily/weekly baseline,
    # circuit breaker, storico trade, Kelly, metriche di performance). Senza
    # questo file il CB daily/weekly si azzera a ogni restart.
    risk_state_path: Optional[Path] = None
    # curva equity persistita (Q5b, docs/53 §0.4): senza, le metriche `eq_*` si
    # azzerano a ogni riavvio e `eq_warm` non diventa mai True su un bot che
    # riparte spesso — cioe' proprio quando servirebbe.
    equity_path: Optional[Path] = None
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
        # ResourceSupervisor (iniettato da TradeOrchestrator.start_all): adatta
        # l'intervallo di tick alla pressione di RAM/CPU del nodo.
        self._supervisor = None
        # Cap di esposizione A LIVELLO DI CONTO (docs/55 Q6): il tetto per bot
        # esiste (`trend.py:493`, default spento) ma con piu' bot sullo stesso
        # conto NESSUNO vede la somma. Il registro condiviso lo inietta il nodo,
        # come per `_supervisor`: None = nessun cap, comportamento invariato.
        self.exposure = None
        self._last_error: str = ""
        # rate-limit dei log di errore (chiave -> ultimo ts loggato)
        self._err_log_ts: Dict[str, float] = {}
        # stop-loss gia' scattato (persistente: non rivende dopo un restart)
        self._stop_loss_triggered = False
        # portfolio manager anti-deadlock (capitale virtuale + preflight dedup)
        self.portfolio = PortfolioManager(quote=self.cfg.symbol.split("/")[-1])

        self.state = BotState(symbol=config.symbol, start_ts=self._now())
        self.store = StateStore(Path(config.state_path)) if config.state_path else None
        self.risk_store = (StateStore(Path(config.risk_state_path))
                           if config.risk_state_path else None)
        self.equity_store = (StateStore(Path(config.equity_path))
                             if config.equity_path else None)
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

        # Misura ONESTA (docs/53 §0.4): la performance si deriva dalla curva
        # equity mark-to-market, non dai PnL per-trade che `domain/equity.py`
        # dichiara inaffidabili (non registrano gli stop-loss, si azzerano a ogni
        # riavvio, mescolano euro e percentuali). La primitiva esisteva ed era
        # usata SOLO dai test: da qui entra nel percorso live.
        self.equity_tracker = EquityTracker()

        self._load_state()
        # Se lo stato contiene una posizione aperta, va restituita alla policy
        # CON il suo stop PRIMA di ogni altra cosa: senza, la policy la
        # adotterebbe ancorando lo stop a 2 ATR invece del trailing che aveva.
        self._ripristina_posizione()
        self._load_risk_state()
        self._load_equity_curve()
        self._rebuild_from_exchange()

    # --- persistence ---------------------------------------------------------

    def _load_state(self) -> None:
        if self.store is None:
            return
        data = self.store.load()
        if isinstance(data, dict) and data.get("symbol"):
            self.state = BotState.from_dict(data)

    def _ripristina_posizione(self) -> None:
        """Restituisce alla policy una posizione aperta sopravvissuta a un riavvio.

        Lo stop monitorato vive solo in memoria. Senza questo ripristino, dopo un
        riavvio la policy adotta la posizione ancorando lo stop a
        prezzo - stop_atr_mult*ATR (2 ATR), mentre il trailing userebbe trail_mult
        (3 ATR): la protezione diventa piu' STRETTA del dovuto e la posizione esce
        in anticipo.
        """
        pos = self.state.posizione_aperta or {}
        try:
            entry = float(pos.get("entry") or 0.0)
            stop = float(pos.get("stop") or 0.0)
        except (TypeError, ValueError):
            return
        if entry <= 0:
            return
        fn = getattr(self.policy, "ripristina_posizione", None)
        if fn is None:
            return
        try:
            if fn(entry, stop):
                log.info("%s: posizione RIPRISTINATA (entry %.6f, stop %.6f)",
                         self.cfg.symbol, entry, stop)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: ripristino posizione fallito: %s", self.cfg.symbol, e)

    def _load_risk_state(self) -> None:
        """Ripristina peak/daily/weekly baseline, CB e storico trade.

        Round-trip verificato: se il file e' assente/corrotto si resta sulla
        baseline costruita in `__init__` (capitale del bot, NON i default 100.0
        della dataclass). Uno stato CB illeggibile viene ricostruito APERTO
        (fail-safe: non tradare su un rischio che non sappiamo interpretare).
        """
        if self.risk_store is None:
            return
        data = self.risk_store.load()
        if not isinstance(data, dict) or not data:
            return
        try:
            self.risk_state = CoreState.from_dict(data, self.risk_state)
        except Exception as e:  # noqa: BLE001 - stato corrotto: si riparte
            log.warning("risk_state %s illeggibile (%s): baseline ripristinata",
                        self.cfg.symbol, e)

    def _load_equity_curve(self) -> None:
        """Ripristina la curva equity (Q5b, docs/53 §0.4).

        Senza questo, a ogni riavvio la serie riparte da zero e `eq_warm`
        (30 campioni o 5 giorni osservati) non diventa mai True: le metriche
        oneste resterebbero non pubblicabili proprio sui bot che si riavviano.
        Una serie illeggibile NON viene inventata: si riparte vuoti e lo si dice.
        """
        if self.equity_store is None:
            return
        data = self.equity_store.load()
        righe = data.get("rows") if isinstance(data, dict) else data
        if not isinstance(righe, list) or not righe:
            return
        try:
            self.equity_tracker.extend(
                [(float(r[0]), float(r[1])) for r in righe])
        except Exception as e:  # noqa: BLE001 - serie corrotta: si riparte
            log.warning("equity_curve %s illeggibile (%s): si riparte vuota",
                        self.cfg.symbol, e)

    def _save_state(self) -> None:
        if self.store is not None:
            self.store.save(self.state.to_dict())
        if self.risk_store is not None:
            self.risk_store.save(self.risk_state.to_dict())
        if self.equity_store is not None:
            self.equity_store.save({"rows": self.equity_tracker.rows})

    async def _journal(self, event: str, **fields) -> None:
        """Append al journal FUORI dall'event loop.

        `Journal.append` fa `flush + os.fsync` per ogni riga: eseguito sul
        thread dell'event loop blocca TUTTI i bot del nodo per alcuni ms a ogni
        ordine. Con N bot che journalizzano ogni tick la latenza si somma.
        """
        if self.journal is None:  # attenzione: Journal ha __len__ → non usare `not`
            return
        record = {"event": event, "symbol": self.cfg.symbol, "ts": self._now(), **fields}
        await asyncio.to_thread(self.journal.append, record)

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
                    # `kind` ignoto: l'ordine arriva dall'exchange, non dal
                    # nostro journal. Viene contato come "non classificato" dalla
                    # scala di vendita, che quindi resta sospesa finche' non si
                    # risolve → impedisce di duplicare la scala a ogni restart.
                    # R3 (docs/53 §0.6): l'ordine arriva dall'exchange, non dal
                    # nostro journal, quindi il prezzo d'ingresso NON e' noto.
                    # Prima si inventava `price * 0.99`: da un entry price
                    # fabbricato discende un PnL fabbricato, e la telemetria
                    # pubblica una performance che non e' quella del conto.
                    # Si dichiara l'ignoto e lo si propaga a chi deve misurarlo.
                    self.state.open_sells[oid] = {
                        "amount": amount, "entry_price": None,
                        "price": price, "target_price": price,
                        "kind": "unknown", "timestamp": self._now(),
                        "entry_unknown": True}
        except Exception as e:  # noqa: BLE001
            log.warning("rebuild open orders fallito: %s", e)
        # 3) la posizione detenuta va riconciliata con l'ASSET REALE
        self._riconcilia_posizione()

    def _riconcilia_posizione(self) -> None:
        """Azzera una posizione che lo stato dice aperta ma che non esiste.

        Se mentre il nodo era fermo l'asset e' stato venduto (a mano, o da un
        altro processo), lo stato resta "in posizione" per sempre: la policy
        pubblica uno stop SOTTO il mercato che, con il trailing che sale insieme
        al prezzo, non scattera' mai, e il bot non entrera' mai piu' su questo
        simbolo. E' un blocco definitivo, non un errore transitorio.

        Se il saldo non e' leggibile NON si azzera nulla: meglio uno stato
        prudente che una posizione vera dimenticata.
        """
        if self.state.posizione_aperta is None:
            return
        base = self.cfg.symbol.split("/")[0]
        try:
            bal = self.ex.fetch_balance()
            libero = float((bal.get("free", {}) or {}).get(base, 0.0) or 0.0)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: riconciliazione posizione impossibile (%s): "
                        "lo stato resta", self.cfg.symbol, e)
            return
        soglia = 0.0
        mfn = getattr(self.ex, "min_amount_for", None)
        if mfn is not None:
            try:
                soglia = float(mfn(self.cfg.symbol) or 0.0)
            except Exception:  # noqa: BLE001
                soglia = 0.0
        if libero > 0 and (soglia <= 0 or libero >= soglia):
            return                      # la posizione c'e' davvero
        log.warning("%s: stato con posizione aperta ma solo %.8f %s liberi "
                    "(soglia %.8f) - posizione AZZERATA per non restare bloccati",
                    self.cfg.symbol, libero, base, soglia)
        self.state.posizione_aperta = None
        fn = getattr(self.policy, "azzera_posizione", None)
        if fn is not None:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                log.warning("%s: azzera_posizione fallito: %s", self.cfg.symbol, e)

    # --- equity --------------------------------------------------------------

    def _default_equity(self) -> float:
        """Equity di default = capitale (senza porta equity dedicata)."""
        return self.cfg.capital

    # --- tick -----------------------------------------------------------------

    async def tick(self) -> None:
        """Un ciclo completo: risk → prezzo → decisione → esecuzione → health."""
        now = self._now()
        # l'errore e' PER-TICK: si azzera qui (non a fine tick), cosi' health e
        # log riflettono l'esito del tick appena concluso invece di essere
        # cancellati prima della scrittura (bug: errori di piazzamento invisibili)
        self._last_error = ""
        # equity reale: get_equity puo' fare I/O (fetch live) → to_thread
        raw_equity = await asyncio.to_thread(self._get_equity)
        equity = await self._guard_equity(raw_equity)
        if equity is None:
            # C7: equity inattendibile ⇒ NESSUN ordine in questo tick e nessuna
            # baseline aggiornata. In health si scrive il valore GREZZO letto
            # (non un sostituto), cosi' la telemetria resta fedele al conto.
            await self._persist(raw_equity if raw_equity == raw_equity else 0.0,
                                blocked=True)
            return
        # campione della curva equity: si registra solo qui, dopo il guard, cosi'
        # le letture sporche non avvelenano le metriche
        self.equity_tracker.append(now, equity)
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
            await self._persist(equity, blocked=True)
            return

        # 2) prezzo (hub con cache, fallback fetch)
        try:
            bal = await asyncio.to_thread(self.ex.fetch_balance)
            # valuta di QUOTAZIONE del simbolo, non EUR hardcoded: un bot
            # SOL/USDT leggeva free=0.0 e appariva sempre senza capitale.
            quote = self._quote
            free = float((bal.get("free", {}) or {}).get(quote) or 0)
            total = float((bal.get("total", {}) or {}).get(quote) or 0)
        except Exception as e:  # noqa: BLE001
            self._note_error(f"balance: {e}")
            await self._persist(equity, blocked=False)
            return

        # aggiorna il portfolio con i dati gia' in mano (niente API extra)
        try:
            orders = await asyncio.to_thread(self.ex.fetch_open_orders, self.cfg.symbol)
            self.portfolio.update(free, orders)
        except Exception:  # noqa: BLE001 - il preflight usera' solo free
            orders = None
            self.portfolio.update(free, [])
        try:
            if self._price_source is not None:
                # price_source can be sync or async (hub.get_price is async)
                price_val = self._price_source()
                if asyncio.iscoroutine(price_val):
                    price = float(await price_val)
                else:
                    price = float(price_val)
            else:
                t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                price = float(t["last"])
        except Exception as e:  # noqa: BLE001
            self._note_error(f"ticker: {e}")
            await self._persist(equity, blocked=False)
            return

        # 2b) PREZZO NON DISPONIBILE: non si decide su un prezzo finto.
        #     Prima il tick proseguiva con price=0.0: la policy rispondeva
        #     "prezzo non valido", health restava "running" con error="" e il
        #     bot era di fatto inerte senza che nulla lo segnalasse (visto in
        #     produzione il 2026-09-13 su XRP/ETH: price=0.000000 per giorni).
        if price <= 0:
            self._note_error("prezzo non disponibile (hub/REST)")
            await self._persist(equity, blocked=False, free_quote=free)
            return

        # DEBUG: log price fetch
        log.info("TICK %s: price=%.6f free=%.4f equity=%.4f", self.cfg.symbol, price, free, equity)

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

        # DEBUG: log decision for VAGR and IRFMR
        if hasattr(self.policy, 'regime') and hasattr(self.policy, 'atr'):
            # VAGR policy
            log.info("VAGR %s: price=%.6f regime=%s atr=%.6f std=%.6f reason=%s to_place=%d to_sell=%d",
                     self.cfg.symbol, price, self.policy.regime, self.policy.atr, self.policy.std_tr,
                     decision.reason, len(decision.to_place), len(decision.to_sell))
        elif hasattr(self.policy, '_z') and hasattr(self.policy, '_inventory'):
            # IRFMR policy
            z_val = 0.0
            if hasattr(self.policy._z, 'mean') and self.policy._z.count > 1:
                std = (self.policy._z.var ** 0.5) if self.policy._z.var > 0 else 0
                if std > 0:
                    z_val = (price - self.policy._z.mean) / std
            log.info("IRFMR %s: price=%.6f z=%.2f inv=%.4f reason=%s to_place=%d to_sell=%d",
                     self.cfg.symbol, price, z_val, self.policy._inventory,
                     decision.reason, len(decision.to_place), len(decision.to_sell))

        # 3a-0) STOP MONITORATO: le policy che escono a trigger (trend) NON
        #       emettono una vendita limite — un limite sotto il mercato si
        #       riempirebbe SUBITO al miglior bid, vendendo al prezzo sbagliato.
        #       Emettono un LIVELLO: se il prezzo lo attraversa, la posizione si
        #       chiude a MERCATO. Si esegue anche in SafeMode: e' la gestione di
        #       una posizione esistente, non un trade nuovo.
        stop_price = getattr(decision, "stop_price", None)
        if (stop_price and float(stop_price) > 0 and price > 0
                and price <= float(stop_price)):
            chiuso = await self._esegui_stop_monitorato(price, float(stop_price))
            if chiuso:
                decision.to_place = []
                decision.to_sell = []
                decision.to_cancel_sell = []
                decision.reason = ("trend: STOP %.6f attraversato (prezzo %.6f)"
                                   % (float(stop_price), price))

        # 3a-1) Il livello di stop della posizione aperta va TENUTO AGGIORNATO
        #       nello stato: e' l'unico posto in cui sopravvive a un riavvio.
        #       Senza, al restart la policy ancorerebbe lo stop a 2 ATR invece
        #       del trailing a 3 ATR che aveva (protezione piu' stretta del
        #       dovuto, quindi uscita in anticipo).
        if decision.stop_price and self.state.posizione_aperta:
            try:
                self.state.posizione_aperta["stop"] = float(decision.stop_price)
            except (TypeError, ValueError):
                pass

        # 3a) Nessun NUOVO trade se la RAM e' critica o se lo stop-loss del bot e'
        #     in corso. `trading_paused` e' un flag IN MEMORIA, che
        #     `_propagate_safemode` (denaro_node.py:478) riscrive a ogni cambio di
        #     livello RAM: da solo non basta, perche' al ritorno a "nominal"
        #     riabiliterebbe gli ordini con lo stop ancora da completare.
        #     R2 (docs/53 §0.6): il blocco deve dipendere anche dallo stato
        #     PERSISTITO. Le posizioni esistenti continuano a essere gestite.
        if self.trading_paused or self.state.stop_loss_triggered:
            decision.to_place = []
            decision.to_sell = []
            decision.reason = "safemode: trading paused"

        # 3a-bis) CAP DI ESPOSIZIONE DI CONTO (docs/55 Q6). Il tetto e' sul
        #     TOTALE NOZIONALE impegnato dai bot che condividono il conto, non
        #     sul numero di bot e non sul singolo: un bot che porterebbe il
        #     totale oltre il cap non apre. Senza registro iniettato
        #     (`self.exposure is None`) il comportamento resta quello storico.
        if self.exposure is not None and decision.to_place:
            nuovo = 0.0
            for _lv in decision.to_place:
                try:
                    nuovo += float(_lv.amount) * float(_lv.buy_price)
                except (TypeError, ValueError):
                    continue
            if not self.exposure.can_open(self.cfg.bot_key, nuovo):
                decision.to_place = []
                decision.reason = (
                    "cap di esposizione di conto: "
                    f"{self.exposure.total():.2f} + {nuovo:.2f} > "
                    f"{self.exposure.cap:.2f}")
                await self._journal("exposure_cap_blocked",
                                    richiesto=round(nuovo, 6),
                                    impegnato=round(self.exposure.total(), 6),
                                    cap=round(self.exposure.cap, 6))
            else:
                self.exposure.commit(self.cfg.bot_key, nuovo)

        # 3aa) GRID BILATERALE: i SELL ladder NON richiedono EUR (usano l'asset
        #      in mano) → si eseguono SEMPRE, anche se il preflight blocca i
        #      buy per mancanza di free (es. ADA con 0 EUR e 9.8 ADA free).
        # 3a-0) ri-ancoraggio della scala: cancella i ladder stantii richiesti
        #       dalla policy (mercato uscito dalla banda) PRIMA di ri-piazzare,
        #       cosi' il conteggio dei livelli occupati nel prossimo tick e'
        #       coerente e non si sommano due scale.
        for oid in getattr(decision, "to_cancel_sell", []):
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
            except Exception as e:  # noqa: BLE001
                if not isinstance(e, PermanentExchangeError):
                    self._note_error(f"cancel ladder {oid}: {e}")
            self.state.open_sells.pop(oid, None)
            await self._journal("ladder_canceled", order_id=oid)

        ladder_ok = 0
        ladder_err = ""
        ladder_levels = list(getattr(decision, "to_sell_levels", []) or [])
        for idx, item in enumerate(decision.to_sell):
            amount, sell_price, level = _sell_parts(item)
            if level < 0 and idx < len(ladder_levels):
                level = int(ladder_levels[idx])
            try:
                o = await asyncio.to_thread(
                    self.ex.create_limit_order, self.cfg.symbol, "sell",
                    amount, sell_price)
                if o:
                    # `price` (prezzo dell'ordine) + `kind`/`level` rendono la
                    # scala ricostruibile e deduplicabile: prima qui si salvava
                    # solo `target_price`, che grid.py non leggeva.
                    self.state.open_sells[o["id"]] = {
                        "amount": amount, "entry_price": price,
                        "price": sell_price, "target_price": sell_price,
                        "kind": "ladder", "level": level,
                        "timestamp": self._now()}
                    await self._journal("sell_placed", order_id=o["id"],
                                        amount=amount, price=sell_price,
                                        level=level, kind="ladder")
                    ladder_ok += 1
            except Exception as e:  # noqa: BLE001
                ladder_err = ladder_err or str(e)[:160]
        # Il log riportava SEMPRE "N piazzati" (len della decisione) anche con
        # 0 ordini accettati: un fallimento totale appariva come successo.
        if decision.to_sell:
            n = len(decision.to_sell)
            if ladder_ok == n:
                log.info("grid bilaterale %s: %d sell ladder piazzati",
                         self.cfg.symbol, n)
            elif ladder_ok:
                log.warning("grid bilaterale %s: %d/%d sell ladder piazzati (%s)",
                            self.cfg.symbol, ladder_ok, n, ladder_err)
                self._note_error(f"ladder sell parziale: {ladder_err}")
            else:
                self._note_error(f"ladder sell rifiutati ({n}): {ladder_err}")

        # 3b) PRE-FLIGHT anti-deadlock (ATLAS v6): fattibilita' BUY prima
        #     delle API. Capitale usabile = free + locked×0.85 (ordini buy
        #     cancellabili); dedup degli ordini speculari (buy sopra il mercato).
        #     NOTA: i fill dei buy aperti vanno processati PRIMA del preflight,
        #     altrimenti un bot con free negativo (asset in mano dopo un fill)
        #     viene bloccato dal preflight e non converte mai i buy in sell.
        await self._process_fills(price, open_orders=orders)
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
                        await self._journal("buy_canceled", order_id=oid)
                    except Exception:  # noqa: BLE001
                        pass
                await self._persist(equity, blocked=False, free_quote=free)
                return
        if decision.to_place:
            decision.to_place = [l for l in decision.to_place
                                 if min_notional <= 0 or l.notional >= min_notional]

        # 4) esecuzione
        for oid in decision.to_cancel:
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
                self.state.open_buys.pop(oid, None)
                await self._journal("buy_canceled", order_id=oid)
            except PermanentExchangeError:
                # Ordine inesistente/invalido: il retry non puo' cambiare
                # l'esito. Rimuovilo dallo stato locale e prosegui, altrimenti
                # resta per sempre in open_buys e blocca l'invariante di griglia.
                # NB: qui c'era `KrakenPermanentError`, MAI importato → il tick
                # moriva con NameError sul ramo di cancel.
                self.state.open_buys.pop(oid, None)
                await self._journal("buy_canceled", order_id=oid)
                log.warning("cancel %s: errore permanente, rimosso da open_buys", oid)
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
                    await self._journal("buy_placed", order_id=o["id"],
                                        amount=level.amount, price=level.buy_price,
                                        level=level.level)
            except Exception as e:  # noqa: BLE001
                self._last_error = f"place buy: {e}"

        # 5) fill processing post-place (se applicabile)
        await self._process_fills(price)

        await self._persist(equity, blocked=False, free_quote=free)

    def _note_error(self, msg: str) -> None:
        """Registra l'errore del tick e lo logga (max 1 volta ogni 5 min).

        Prima: gli errori di piazzamento finivano solo in health e venivano
        azzerati a fine tick; i fallimenti ripetuti (es. ladder sell dust
        rifiutati ogni 30s) erano completamente invisibili nei log.
        """
        if not self._last_error:
            self._last_error = msg
        key = msg.split(":")[0][:48]
        now = self._now()
        last = self._err_log_ts.get(key, 0.0)
        if now - last > 300.0:
            self._err_log_ts[key] = now
            log.warning("%s %s: %s", self.cfg.symbol, key, msg[:300])

    async def _guard_equity(self, equity: float) -> "float | None":
        """P2 — sanity dell'equity. Ritorna l'equity se plausibile, **None** se
        inattendibile: in quel caso il tick viene saltato e nessun ordine parte.

        Range plausibile per conti micro: [5% , 30×] del capitale — evita che
        una lettura sporca avveleni peak/daily/weekly baseline (bug
        weekly_loss_-99% visto in produzione su DOGE nuvola).

        C7 (revisione esterna 2026-09-15): prima, su lettura sospetta, si
        restituiva l'ultimo valore valido o — in mancanza — il capitale di
        configurazione. Cosi' drawdown, circuit breaker e stop-loss venivano
        calcolati su un numero inventato e *stabile*, e il rischio reale
        spariva dalla metrica. Osservato dal vivo su mc2: "equity sospetta
        0.0852 per SOL/EUR -> uso 12.0000" migliaia di volte, con 0.0005 EUR
        liberi reali. Ora non si sostituisce nulla: si salta il tick.

        Fix B1 (2026-09-07): per exchange live (Kraken/OKX), se l'equity bassa
        e' coerente con free+asset*price (capitale reale spostato in asset),
        trustarla invece di usare il fallback. Questo evita il preflight blocker
        per bot trend con equity libera bassa ma posizione in asset consistente.
        Per paper exchange l'equity e' calcolata localmente ed e' sempre coerente.

        ASYNC (fix critico): la versione sincrona chiamava `fetch_balance()` —
        `time.sleep` di rate-limit/retry inclusi — SUL THREAD DELL'EVENT LOOP,
        bloccando TUTTI i bot del nodo quando l'equity usciva dal range. Inoltre
        il check di coerenza era codice morto per gli adapter live: testava
        `iscoroutinefunction(price)` su un OGGETTO coroutine (il risultato della
        chiamata), non sulla funzione, quindi cadeva sempre in `except`.
        """
        cap = max(1e-9, self.cfg.capital)
        lo, hi = cap * 0.05, cap * 30.0
        if equity is not None and equity == equity and lo < equity <= hi:
            self._last_sane_equity = equity
            return equity

        from ..infrastructure.exchanges.paper import PaperExchange
        if not isinstance(self.ex, PaperExchange):
            try:
                bal = await asyncio.to_thread(self.ex.fetch_balance)
                base, quote = (self.cfg.symbol.split("/") + ["EUR"])[:2]
                free_q = float((bal.get("free", {}) or {}).get(quote) or 0)
                free_b = float((bal.get("free", {}) or {}).get(base) or 0)
                ref = price = 0.0
                if self._price_source is not None:
                    ref = self._price_source()
                    price = float(await ref) if asyncio.iscoroutine(ref) else float(ref)
                else:
                    t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                    price = float(t["last"])
                if price > 0:
                    estimated = free_q + free_b * price
                    # tolleranza 20%: se l'equity e' coerente con la posizione
                    # reale (capitale spostato in asset) la si accetta.
                    if estimated > 0 and abs(equity - estimated) / estimated < 0.2:
                        log.info("equity coerente con free+asset*price "
                                 "(%.4f~=%.4f) per %s — trust",
                                 equity, estimated, self.cfg.symbol)
                        self._last_sane_equity = equity
                        return equity
            except Exception:  # noqa: BLE001
                pass  # fallback al comportamento originale
        # C7: nessun valore sostitutivo. Un'equity che non si riesce a
        # verificare non e' un'equity su cui decidere.
        log.warning("equity inattendibile %.4f per %s: tick saltato "
                    "(nessun valore sostitutivo)", equity, self.cfg.symbol)
        self._last_error = f"equity inattendibile: {equity:.4f}"
        return None

    async def _persist(self, equity: float, blocked: bool,
                       free_quote: float = 0.0) -> None:
        """Scrive stato + risk_state + health FUORI dall'event loop.

        `_save_state` fa due scritture atomiche (tmp+rename) e `_write_health`
        una terza: eseguirle sul thread dell'event loop serializza il disco su
        tutti i bot del nodo. Un unico `to_thread` le raggruppa.
        """
        def _write() -> None:
            self._save_state()
            self._write_health(equity, blocked=blocked, free_quote=free_quote)

        await asyncio.to_thread(_write)

    @property
    def _quote(self) -> str:
        """Valuta di quotazione del simbolo (fallback EUR per i simboli nudi)."""
        return self.cfg.symbol.split("/")[-1] if "/" in self.cfg.symbol else "EUR"

    async def _notify_fill(self, order_id: str, side: str, price: float,
                           size: float, fee: float = 0.0) -> None:
        """Notifica il fill alla policy (contratto `Policy.on_fill`).

        Le firme delle policy sono storicamente eterogenee:
        - VAGR/IRMR/MinCapture: `on_fill(order_id, side, price, size)`
        - AdaptiveVolGrid:      `on_fill(side, price, qty, fee, ts)`
        - CyclePhaseGrid:       `on_fill(fill: dict)`
        Si prova il bind della firma reale invece di indovinare, cosi' una
        policy nuova non deve adattarsi. Qualsiasi errore della policy NON deve
        far fallire il tick (la contabilita' autorevole e' nel Journal).
        """
        fn = getattr(self.policy, "on_fill", None)
        if fn is None:
            return
        ts = self._now()
        payload = {"order_id": order_id, "side": side, "price": price,
                   "size": size, "fee": fee, "ts": ts}
        # NB: l'arity da sola NON basta a disambiguare — `(order_id, side,
        # price, size)` e `(side, price, qty, fee, ts)` collidono quando fee/ts
        # non hanno default. Si dispatcha quindi sui NOMI dei parametri.
        values = {
            "order_id": order_id, "oid": order_id, "id": order_id,
            "side": side,
            "price": price, "entry": price, "fill_price": price,
            "size": size, "amount": size, "qty": size, "quantity": size,
            "fee": fee, "fees": fee,
            "ts": ts, "timestamp": ts, "now": ts,
        }
        signature = None
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):  # pragma: no cover - builtins
            signature = None

        if signature is not None:
            params = [p for p in signature.parameters.values()
                      if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                    inspect.Parameter.KEYWORD_ONLY)]
            has_var_positional = any(
                p.kind == inspect.Parameter.VAR_POSITIONAL
                for p in signature.parameters.values())

            if not params and has_var_positional:
                params = []          # `on_fill(*args)`: usa il fallback posizionale
            elif len(params) == 1 and params[0].name in (
                    "fill", "record", "data", "event", "payload"):
                self._call_on_fill(fn, payload)
                return
            elif params:
                kwargs = {}
                for p in params:
                    if p.name in values:
                        kwargs[p.name] = values[p.name]
                    elif (p.default is inspect.Parameter.empty
                          and p.kind is not inspect.Parameter.KEYWORD_ONLY):
                        kwargs = None
                        break
                if kwargs is not None:
                    self._call_on_fill(fn, kwargs)
                    return

        # Ultimo tentativo: le due firme posizionali storiche.
        for args in ((order_id, side, price, size),
                     (side, price, size, fee, ts),
                     (side, price, size),
                     (payload,)):
            try:
                fn(*args)
            except TypeError:
                continue
            except Exception as e:  # noqa: BLE001
                log.warning("policy.on_fill(%s) fallito: %s", self.cfg.symbol, e)
            return

    @staticmethod
    def _call_on_fill(fn, arg) -> None:
        try:
            if isinstance(arg, dict):
                fn(**arg)
            else:
                fn(*arg)
        except Exception as e:  # noqa: BLE001 - la contabilita' e' nel Journal
            log.warning("policy.on_fill fallito: %s", e)

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

    async def _esegui_stop_monitorato(self, price: float,
                                      stop_price: float) -> bool:
        """Chiude a MERCATO la posizione perche' il prezzo ha toccato lo stop.

        Ritorna True se la posizione risulta chiusa (o se non c'era nulla da
        chiudere), False se il tentativo va ritentato al tick successivo.

        Perche' a MERCATO e non con un ordine limite: lo stop e' un livello
        SOTTO il prezzo, e un limite di vendita sotto il mercato si riempie
        immediatamente al miglior bid — cioe' subito, al prezzo sbagliato. Il
        costo dell'uscita a mercato e' limitato dal guard di spread, lo stesso
        usato dallo stop-loss di bot.
        """
        # 1) nessuna vendita limite deve restare in giro
        for oid in list(self.state.open_sells):
            try:
                await asyncio.to_thread(self.ex.cancel_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                pass
            self.state.open_sells.pop(oid, None)

        # 2) guard di spread: non vendere in un mercato impazzito
        max_slip = getattr(self.cfg, "max_slippage", 0.0) or 0.0
        if max_slip > 0:
            try:
                t = await asyncio.to_thread(self.ex.fetch_ticker, self.cfg.symbol)
                bid = float(t.get("bid") or 0.0)
                ask = float(t.get("ask") or 0.0)
                if bid > 0 and ask > 0:
                    spread = (ask - bid) / ((ask + bid) / 2.0)
                    if spread > max_slip:
                        await self._journal("trend_stop_blocked_slippage",
                                            spread=round(spread, 6),
                                            max_slippage=max_slip)
                        return False
            except Exception:  # noqa: BLE001
                pass  # fail-open: meglio uscire che restare esposti

        # 3) quantita' da vendere = la SIZE DELLA POSIZIONE, non il saldo del conto.
        #    R1 (docs/53 §0.6): vendere il saldo LIBERO liquida a mercato anche il
        #    capitale di un altro bot sullo stesso sub-account, o asset detenuti a
        #    mano. Questo bot risponde solo della propria size.
        base = self.cfg.symbol.split("/")[0]
        try:
            bal = await asyncio.to_thread(self.ex.fetch_balance)
            libero = float((bal.get("free", {}) or {}).get(base, 0.0) or 0.0)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"trend stop balance: {e}"
            return False

        pos = self.state.posizione_aperta or {}
        entrata = float(pos.get("entry") or 0.0)
        size_posizione = float(pos.get("amount") or 0.0)
        if size_posizione <= 0:
            # Nessuna posizione tracciata: NON si liquida un saldo sconosciuto.
            # Meglio una posizione da riconciliare che un conto svuotato.
            await self._journal("stop_no_position", libero=libero)
            self._last_error = ("stop senza posizione tracciata: nessuna vendita "
                                "(saldo libero non toccato)")
            log.error("TREND STOP %s: posizione non tracciata, nessuna vendita "
                      "(libero %.8f lasciato intatto)", self.cfg.symbol, libero)
            return False
        amount = min(libero, size_posizione)
        if amount < size_posizione:
            await self._journal("stop_partial_close", richiesto=size_posizione,
                                disponibile=libero, venduto=amount)
            log.warning("TREND STOP %s: venduto %.8f dei %.8f della posizione "
                        "(libero insufficiente)", self.cfg.symbol, amount,
                        size_posizione)
        if amount > 0:
            try:
                await asyncio.to_thread(self.ex.sell_market, self.cfg.symbol, amount)
            except Exception as e:  # noqa: BLE001
                self._last_error = f"trend stop sell: {e}"
                log.error("TREND STOP %s: vendita fallita: %s", self.cfg.symbol, e)
                return False
        else:
            log.warning("TREND STOP %s: nessun %s libero da vendere (amount=0); "
                        "controlla ordini aperti/posizioni residue",
                        self.cfg.symbol, base)

        # 4) contabilita' fee-aware, identica al fill di una vendita tracciata
        profit = 0.0
        if amount > 0:
            cost = amount * entrata * (1 + self.cfg.fee) if entrata > 0 else 0.0
            proceeds = amount * price * (1 - self.cfg.fee)
            profit = proceeds - cost if entrata > 0 else 0.0
            self.state.total_pnl += profit
            self.state.total_trades += 1
            if profit >= 0:
                self.state.wins += 1
            else:
                self.state.losses += 1
            self.state.volume += amount * price
            if entrata > 0:
                # P5: metriche di performance (Sharpe/Sortino/Calmar)
                self.risk_state.trade_results.append(profit)
                try:
                    self.risk_state.perf.update(
                        profit / max(1e-9, self.cfg.capital))
                    self.risk_state.perf.recalc_ratios(
                        self.risk_state.trade_results,
                        self.risk_state.peak_capital,
                        self.risk_state.current_capital,
                        self.risk_state.initial_capital)
                except Exception:  # noqa: BLE001
                    pass
        self.state.posizione_aperta = None
        await self._journal("trend_stop_sell", amount=amount, price=price,
                            stop=stop_price, entry=entrata or None,
                            profit=round(profit, 8))
        # notifica la policy: con side="sell" azzera in_posizione e stop, quindi
        # il tick successivo riparte flat e puo' cercare un nuovo breakout.
        await self._notify_fill("stop", "sell", price, amount,
                                fee=amount * price * self.cfg.fee)
        return True

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
                    ref = self._price_source()
                    # `price_source` e' ASYNC per i bot live (hub.get_price):
                    # `float(coroutine)` sollevava TypeError e il prezzo finiva
                    # sempre a 0.0 nel journal dello stop-loss.
                    price = float(await ref) if asyncio.iscoroutine(ref) else float(ref)
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
                        await self._journal("stop_loss_blocked_slippage",
                                            spread=round(spread, 4),
                                            max_slippage=max_slip)
                        await self._persist(equity, blocked=True)
                        return
            except Exception:  # noqa: BLE001
                pass  # fail-open: non misurabile → procedi

        # 2) vendi l'asset posseduto (free balance del base asset)
        base = self.cfg.symbol.split("/")[0]
        try:
            bal = await asyncio.to_thread(self.ex.fetch_balance)
            libero = float((bal.get("free", {}) or {}).get(base, 0.0) or 0.0)
            # R1 (docs/53 §0.6): si vende la SIZE DELLA POSIZIONE, non il saldo.
            # Il libero puo' includere l'asset di un altro bot sullo stesso
            # sub-account, o di una mano umana: questo bot risponde solo della
            # propria size. Se non c'e' posizione tracciata NON si vende nulla.
            _pos = self.state.posizione_aperta or {}
            _size = float(_pos.get("amount") or 0.0)
            amount = min(libero, _size) if _size > 0 else 0.0
            if _size <= 0:
                await self._journal("stop_loss_no_position", libero=libero,
                                    drawdown=round(drawdown, 4))
                log.error("STOP LOSS %s: posizione non tracciata, nessuna vendita "
                          "(libero %.8f lasciato intatto)", self.cfg.symbol, libero)
            elif amount < _size:
                await self._journal("stop_loss_partial_close", richiesto=_size,
                                    disponibile=libero, venduto=amount,
                                    drawdown=round(drawdown, 4))
                log.warning("STOP LOSS %s: venduto %.8f dei %.8f della posizione "
                            "(libero insufficiente)", self.cfg.symbol, amount, _size)
            # se il residuo e' sotto il minimo dell'exchange, un market sell
            # separato fallirebbe (volume minimum not met): su molti exchange la
            # chiusura completa e' accettata anche sotto il minimo nominale.
            min_amt = 0.0
            mfn = getattr(self.ex, "min_amount_for", None)
            if mfn is not None:
                try:
                    min_amt = float(mfn(self.cfg.symbol) or 0.0)
                except Exception:
                    min_amt = 0.0
            if amount > 0:
                if min_amt > 0 and amount < min_amt:
                    log.warning(
                        "STOP LOSS %s: amount %.8f < min %.8f — tentativo market "
                        "sell del totale (chiusura completa posizione)",
                        self.cfg.symbol, amount, min_amt)
                await asyncio.to_thread(self.ex.sell_market, self.cfg.symbol, amount)
                await self._journal("stop_loss_sell", amount=amount,
                                    drawdown=round(drawdown, 4), price=price)
            else:
                log.warning("STOP LOSS %s: nessun %s libero da vendere (amount=0); "
                            "controlla ordini aperti/posizioni residue",
                            self.cfg.symbol, base)
        except Exception as e:  # noqa: BLE001
            self._last_error = f"stop loss sell: {e}"
            log.error("STOP LOSS %s: vendita fallita: %s", self.cfg.symbol, e)
            # R2 (docs/53 §0.6): si RIPROVA. Il ramo di tick esegue lo stop solo
            # se `stop_loss_triggered` e' False, quindi lasciarlo True qui
            # significava NON ritentare mai: il commento precedente prometteva un
            # retry che non avveniva. Stesso schema del guard di spread, che
            # poche righe sopra ripristina il flag con "# riprova".
            # `trading_paused` resta True: nessun NUOVO ordine finche' la
            # posizione non e' chiusa.
            self.state.stop_loss_triggered = False
            await self._journal("stop_loss_sell_failed", error=str(e)[:200],
                                drawdown=round(drawdown, 4))
            await self._persist(equity, blocked=True)
            return

        await self._journal("stop_loss", drawdown=round(drawdown, 4), equity=equity)
        await self._persist(equity, blocked=True)

    async def _process_fills(self, price: float,
                             open_orders: Optional[List[dict]] = None) -> None:
        """Riconcilia gli ordini tracciati con lo stato dell'exchange.

        OTTIMIZZAZIONE CRITICA DI LATENZA (fix 2026-09): la versione precedente
        faceva UNA chiamata REST `fetch_order` per OGNI ordine tracciato, in
        serie: 2×(buy+sell) round-trip per tick, piu' `fetch_balance` e
        `fetch_ticker`. Con la scala di vendita duplicata (bug grid.py) il
        numero di ordini cresceva a ogni tick e il tempo di tick cresceva con
        esso → spirale. Ora si fa UNA `fetch_open_orders` (spesso gia' in cache
        dal chiamante) e si paga `fetch_order` SOLO per gli ordini che sono
        spariti dagli aperti, cioe' solo nel tick in cui qualcosa e' cambiato.
        """
        if open_orders is None:
            try:
                open_orders = await asyncio.to_thread(
                    self.ex.fetch_open_orders, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                open_orders = None
        open_ids: Optional[set] = (None if open_orders is None
                                   else {str(o.get("id")) for o in open_orders})

        _ordini = {}

        async def _resolved_order(oid: str):
            """Dict dell'ordine risolto, o None se ancora aperto/irrisolvibile.

            Q4 (docs/53 §0.6): serve il DICT, non solo lo `status`, perche' e' li'
            che la sede riporta la quantita' DAVVERO riempita (`filled`).
            """
            if open_ids is not None and oid in open_ids:
                return None
            try:
                o = await asyncio.to_thread(self.ex.fetch_order, oid, self.cfg.symbol)
            except Exception:  # noqa: BLE001
                return None
            _ordini[oid] = o
            return o

        async def _resolved_status(oid: str) -> str:
            """'open' se ancora aperto; altrimenti interroga l'ordine singolo."""
            o = await _resolved_order(oid)
            if o is None:
                return "open"  # non risolvibile: non toccare lo stato
            return str(o.get("status", "open"))

        def _filled(oid: str, default: float) -> float:
            """Quantita' RIEMPITA secondo la sede; `default` se non la riporta.

            Solo un valore > 0 e' informazione: un ordine CHIUSO con `filled: 0`
            e' una contraddizione (o un fake che non traccia l'ordine), e li' si
            tiene la quantita' richiesta come prima. Cosi' il caso reale — la
            sede che riempie meno del richiesto — viene contato, e i percorsi che
            non riportano `filled` restano invariati.
            """
            o = _ordini.get(oid) or {}
            for chiave in ("filled", "filled_amount", "executed_amount_base"):
                v = o.get(chiave)
                if v is None:
                    continue
                try:
                    q = float(v)
                except (TypeError, ValueError):
                    continue
                return q if q > 0 else default
            return default

        for oid, info in list(self.state.open_buys.items()):
            st = await _resolved_status(oid)
            # Q4 (docs/53 §0.6): si usa la quantita' RIEMPITA, non quella
            # richiesta. Una sede puo' chiudere un ordine con meno del richiesto,
            # e un ordine cancellato puo' aver riempito in parte: in entrambi i
            # casi il riempito e' denaro vero e non deve sparire dallo stato.
            _filled_qty = _filled(
                oid, float(info["amount"]) if st in ("closed", "filled") else 0.0)
            if st in ("closed", "filled") or _filled_qty > 0:
                entry = float(info["price"])
                amount = _filled_qty
                if getattr(self.policy, "STOP_MONITORATO", False):
                    # La protezione e' uno stop monitorato: NESSUN ordine limite
                    # da piazzare (essendo sotto il mercato si riempirebbe
                    # subito, al prezzo sbagliato). Si registra la posizione: il
                    # livello di stop arriva a ogni tick in stop_price.
                    # Lo stop iniziale si registra SUBITO: la policy lo
                    # conosce (entry - stop_atr_mult*ATR). Lasciandolo a 0,
                    # un riavvio nella finestra fra il fill e il primo tick
                    # ripristinerebbe un trailing a 2.5 ATR invece dello
                    # stop a 2 ATR su cui e' misurata la strategia.
                    stop_iniziale = 0.0
                    _fn_stop = getattr(self.policy, "sell_target", None)
                    if _fn_stop is not None:
                        try:
                            stop_iniziale = float(_fn_stop(entry) or 0.0)
                        except Exception:  # noqa: BLE001
                            stop_iniziale = 0.0
                    if not (0.0 < stop_iniziale < entry):
                        stop_iniziale = 0.0
                    self.state.posizione_aperta = {
                        "entry": entry, "amount": amount,
                        "stop": stop_iniziale, "ts": self._now()}
                    await self._journal("buy_filled", order_id=oid, entry=entry,
                                        amount=amount, sell_target=None,
                                        protezione="stop_monitorato")
                    await self._notify_fill(
                        oid, "buy", entry, amount,
                        fee=amount * entry * self.cfg.fee)
                else:
                    target = self.policy.sell_target(entry)
                    try:
                        sell = await asyncio.to_thread(
                            self.ex.create_limit_order, self.cfg.symbol, "sell",
                            amount, target)
                        if sell:
                            # `kind="tp"` distingue le vendite da take-profit
                            # dalla scala ladder (grid.py conta solo le ladder) e
                            # `price` le rende deduplicabili.
                            self.state.open_sells[sell["id"]] = {
                                "amount": amount, "entry_price": entry,
                                "price": target, "target_price": target,
                                "kind": "tp", "timestamp": self._now()}
                            await self._journal("buy_filled", order_id=oid,
                                                entry=entry, amount=amount,
                                                sell_target=target)
                            await self._notify_fill(
                                oid, "buy", entry, amount,
                                fee=amount * entry * self.cfg.fee)
                    except Exception as e:  # noqa: BLE001
                        self._last_error = f"place sell: {e}"
                self.state.open_buys.pop(oid, None)
            elif st in ("canceled", "expired", "rejected"):
                self.state.open_buys.pop(oid, None)

        for oid, info in list(self.state.open_sells.items()):
            st = await _resolved_status(oid)
            # Q4 (docs/53 §0.6): come per i buy, si contabilizza il RIEMPITO.
            _filled_qty = _filled(
                oid, float(info["amount"]) if st in ("closed", "filled") else 0.0)
            if st in ("closed", "filled") or _filled_qty > 0:
                # PnL fee-aware: proceeds×(1-fee) - cost×(1+fee). Con fee=0
                # il comportamento e' identico all'accounting del motore v3.3.
                amount = _filled_qty
                _entry_raw = info.get("entry_price")
                if _entry_raw is None:
                    # R3 (docs/53 §0.6): prezzo d'ingresso NON noto (posizione
                    # recuperata dall'exchange). Un PnL che non si puo' misurare
                    # si dichiara non misurabile: non si inventa e non entra nei
                    # totali, altrimenti la performance pubblicata e' finta.
                    target = float(info["target_price"])
                    await self._journal("sell_unmeasured", order_id=oid,
                                        amount=amount, exit=target,
                                        motivo="entry_price non noto "
                                               "(posizione recuperata)")
                    await self._notify_fill(oid, "sell", target, amount,
                                            fee=amount * target * self.cfg.fee)
                    self.state.open_sells.pop(oid, None)
                    continue
                entry = float(_entry_raw)
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
                await self._journal("sell_filled", order_id=oid,
                                    amount=amount, entry=entry, exit=target,
                                    profit=profit, total_pnl=self.state.total_pnl)
                await self._notify_fill(oid, "sell", target, amount,
                                        fee=amount * target * self.cfg.fee)
                # P5: performance metrics (Sharpe/Sortino/Calmar/ProfitFactor)
                self.risk_state.trade_results.append(profit)
                pnl_pct = profit / max(1e-9, self.cfg.capital)
                self.risk_state.perf.update(pnl_pct)
                try:
                    self.risk_state.perf.recalc_ratios(
                        self.risk_state.trade_results,
                        self.risk_state.peak_capital,
                        self.risk_state.current_capital,
                        self.risk_state.initial_capital)
                except Exception:  # noqa: BLE001
                    pass
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
        # MISURA ONESTA dalla curva equity (docs/53 §0.4): questi campi derivano
        # dalla serie mark-to-market, non dai PnL per-trade. `eq_warm` dice se la
        # storia basta a dare un numero non truffa: finche' e' False i valori
        # `eq_*` non sono ancora significativi e non vanno letti come performance.
        payload.update(self.equity_tracker.evaluate())
        # POSIZIONE DETENUTA. Per le policy a STOP MONITORATO (trend) quando si e'
        # in posizione NON ci sono ordini aperti: buys e sells restano 0 e la
        # dashboard non poteva distinguere "in posizione" da "flat". Qui si
        # espone lo stato vero, con entry e livello di stop.
        pos = self.state.posizione_aperta or {}
        payload["in_posizione"] = 1 if pos else 0
        # I campi si scrivono SEMPRE (0 quando flat): il feeder Zabbix salta le
        # chiavi assenti, quindi un item che sparisce quando si e' flat andrebbe
        # in "nessun dato" e farebbe scattare il trigger a vuoto.
        try:
            payload["pos_entry"] = round(float(pos.get("entry") or 0.0), 8)
            payload["pos_stop"] = round(float(pos.get("stop") or 0.0), 8)
        except (TypeError, ValueError):
            payload["pos_entry"] = 0.0
            payload["pos_stop"] = 0.0
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
        # P5 — telemetria: Sharpe/Sortino/Calmar/ProfitFactor/WinRate
        try:
            perf = self.risk_state.perf
            payload["sharpe"] = round(float(perf.sharpe_ratio), 3)
            payload["sortino"] = round(float(perf.sortino_ratio), 3)
            payload["calmar"] = round(float(perf.calmar_ratio), 3)
            payload["profit_factor"] = round(float(perf.profit_factor), 3)
            payload["win_rate_pct"] = round(float(perf.win_rate) * 100, 1)
            payload["kelly"] = round(float(self.risk_state.kelly_fraction), 4)
        except Exception:  # noqa: BLE001
            pass
        self.health.write_json(payload)

    # --- run loop ------------------------------------------------------------

    def _tick_interval(self) -> float:
        """Intervallo di tick con backpressure del supervisore.

        Prima il loop usava `cfg.tick_interval` nudo: la RAM non rallentava
        nulla e sotto pressione tutti i bot restavano alla frequenza massima,
        proprio quando serviva alleggerire.
        """
        base = self.cfg.tick_interval
        if self._supervisor is None:
            return base
        try:
            return self._supervisor.adjusted_interval(base)
        except Exception:  # noqa: BLE001
            return base

    async def run(self) -> None:
        self._running = True
        self.state.start_ts = self._now()
        while self._running:
            try:
                await self.tick()
            except Exception as e:  # noqa: BLE001 - il bot non deve morire
                self._last_error = f"tick: {e}"
                log.error("bot %s tick error: %s", self.cfg.symbol, e)
            await asyncio.sleep(self._tick_interval())

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

    def add_ohlcv_source(self, symbol: str, exchange, callback,
                         timeframe: str = "", limit: int = 0) -> None:
        """Alimenta una policy con OHLCV reale (refresh 60s).

        `timeframe` e `limit` sono per-simbolo: la policy adattiva vuole candele
        1h, il trend giornaliero le candele 1d da 300 barre — le STESSE del
        precaricamento all'avvio, altrimenti canale e ATR cambiano sotto i piedi
        al primo refresh.
        """
        self._ohlcv_sources[symbol] = (exchange, callback, timeframe,
                                       limit or self.OHLCV_LIMIT)

    async def _ohlcv_loop(self, symbol: str) -> None:
        exchange, callback, timeframe, limit = self._ohlcv_sources[symbol]
        timeframe = timeframe or self.OHLCV_TIMEFRAME
        # preferisce fetch_ohlcv_raw (bypassa il bug ccxt 4.5.x), fallback
        fetch = getattr(exchange, "fetch_ohlcv_raw", None) or getattr(
            exchange, "fetch_ohlcv", None)
        if fetch is None:
            log.warning("ohlcv %s: exchange senza fetch_ohlcv — canale disattivo",
                        symbol)
            return
        while True:
            try:
                ohlcv = await asyncio.to_thread(fetch, symbol, timeframe,
                                                limit)
                if ohlcv:
                    if inspect.iscoroutinefunction(callback):
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
            bot._supervisor = self._supervisor
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
