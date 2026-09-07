#!/usr/bin/env python3
"""denaro_node.py — il Node asincrono Denaro (M6/M7 del blueprint).

UN processo asyncio per macchina che ospita N bot come task leggeri:
- MarketDataHub (1 canale per exchange, multiplexato)
- ResourceSupervisor (zero OOM, backpressure, throttling adattivo)
- BotTask paper (PaperExchange) o live (OKXAdapter EEA)

Uso:
    python -m denaro.denaro_node --config config/node_paper.json

Nota: va lanciato come modulo (dalla root del repo), non come script,
perche' importa il package `denaro`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List

from denaro.application.config import load_node_config
from denaro.application.orchestrator import BotConfig, BotTask, TradeOrchestrator
from denaro.application.safemode import SafeModeGuardian
from denaro.application.supervisor import ResourceSupervisor
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.exchanges.paper import PaperExchange
from denaro.infrastructure.market_data import MarketDataHub
from denaro.infrastructure.sqlite_store import SqliteStateStore

log = logging.getLogger("denaro.node")

# Chiavi di config dei bot modificabili a runtime via strategy_overrides.json.
# La brain (watchdog/strategy lab) promuove/retrocede strategie scrivendo questo
# file; il Node lo rilegge a ogni avvio di un bot. File assente o corrotto →
# fallback silenzioso alla config YAML (MAI crash del Node).
_OVERRIDE_KEYS = frozenset({
    "strategy", "levels", "capital", "buy_distance", "profit_target",
    "level_step", "retarget_factor", "max_order_age_s",
    "sell_levels", "sell_distance", "sell_step", "sell_asset_share",
    "stop_loss_pct", "daily_loss_limit", "max_drawdown_limit",
    "tick_interval", "fee", "entry_slip", "quote",
})


# --- configurazione ----------------------------------------------------------

def load_config(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_grid_params(bot: dict) -> GridParams:
    return GridParams(
        levels=int(bot.get("levels", 3)),
        buy_distance=float(bot.get("buy_distance", 0.01)),
        profit_target=float(bot.get("profit_target", 0.015)),
        level_step=float(bot.get("level_step", 0.005)),
        retarget_factor=float(bot.get("retarget_factor", 1.5)),
        max_order_age_s=float(bot.get("max_order_age_s", 12 * 3600)),
        # GRID BILATERALE (micro-capitale): scala di vendita dell'asset sopra
        sell_levels=int(bot.get("sell_levels", 0)),
        sell_distance=float(bot.get("sell_distance", 0.02)),
        sell_step=float(bot.get("sell_step", 0.01)),
        sell_asset_share=float(bot.get("sell_asset_share", 1.0)),
    )


def build_policy(bot: dict, exchange):
    """Costruisce la strategia del bot in base a `strategy`:
    grid (default) | momentum | meanrev. I minimi dell'exchange vengono
    passati alla policy per scartare ordini non piazzabili."""
    strategy = bot.get("strategy", "grid")
    fn = getattr(exchange, "min_amount_for", None)
    min_amount = float(fn(bot["symbol"])) if fn is not None else 0.0
    if strategy == "momentum":
        from denaro.domain.momentum import MomentumParams, MomentumPolicy
        return MomentumPolicy(
            MomentumParams(
                profit_target=float(bot.get("profit_target", 0.02)),
                entry_slip=float(bot.get("entry_slip", 0.002)),
            ),
            min_amount=min_amount)
    if strategy == "meanrev":
        from denaro.domain.meanrev import MeanReversionParams, MeanReversionPolicy
        return MeanReversionPolicy(
            MeanReversionParams(
                profit_target=float(bot.get("profit_target", 0.015)),
                entry_slip=float(bot.get("entry_slip", 0.001)),
            ),
            min_amount=min_amount)
    # default: grid
    if strategy == "adaptive":
        from denaro.domain.adaptive import AdaptiveEngine, AdaptiveParams
        return AdaptiveEngine(
            AdaptiveParams(
                levels=int(bot.get("levels", 5)),
                base_buy_distance=float(bot.get("buy_distance", 0.01)),
                profit_target=float(bot.get("profit_target", 0.015)),
            ),
            min_amount=min_amount)
    return GridPolicy(build_grid_params(bot), min_amount=min_amount)


def build_rest_exchange(exchange_cfg: dict):
    """Client REST pubblico per il hub (ticker senza chiavi)."""
    import ccxt
    name = exchange_cfg.get("name", "okx")
    if name == "okx":
        config: Dict[str, Any] = {"enableRateLimit": True}
        if exchange_cfg.get("eea", True):
            config["hostname"] = "eea.okx.com"   # vincolo critico runtime
        return ccxt.okx(config)
    raise ValueError(f"exchange REST non supportato: {name}")


def build_exchange(bot: dict, data_dir: Path):
    """Costruisce l'exchange del bot. Le chiavi LIVE arrivano dall'ambiente
    (EnvironmentFile systemd), MAI dal config versionato.

    `env_prefix` (es. "MARCOSUB1_", "ATLAS_") consente piu' account per lo
    stesso exchange: le chiavi vengono lette da {PREFIX}OKX_API_KEY ecc.
    """
    import os
    prefix = bot.get("env_prefix", "")

    def env(name, default=""):
        return os.getenv(prefix + name, os.getenv(name, default))

    mode = bot.get("mode", "paper")
    symbol = bot["symbol"]
    if mode == "paper":
        return PaperExchange(symbol, capital=float(bot.get("capital", 100)),
                             quote=bot.get("quote", "EUR"))
    if mode == "okx":
        from denaro.infrastructure.exchanges.okx import OKXAdapter
        key = env("OKX_API_KEY", bot.get("api_key", ""))
        secret = env("OKX_API_SECRET", bot.get("api_secret", ""))
        passphrase = env("OKX_PASSPHRASE", bot.get("passphrase", ""))
        if not key or not secret or not passphrase:
            raise ValueError(f"chiavi OKX mancanti per {symbol} (env {prefix}OKX_API_*)")
        return OKXAdapter(api_key=key, secret=secret, passphrase=passphrase)
    if mode == "kraken":
        from denaro.infrastructure.exchanges.kraken import KrakenAdapter
        key = env("KRAKEN_API_KEY", bot.get("api_key", ""))
        secret = env("KRAKEN_API_SECRET", bot.get("api_secret", ""))
        if not key or not secret:
            raise ValueError(f"chiavi Kraken mancanti per {symbol} (env {prefix}KRAKEN_API_*)")
        return KrakenAdapter(api_key=key, secret=secret)
    raise ValueError(f"modalita' bot sconosciuta: {mode}")


def paths_for(bot: dict, data_dir: Path) -> Dict[str, Path]:
    """Path stato/journal/health UNIVOCI per bot (mode + env_prefix + symbol),
    cosi' paper e live sullo stesso symbol non collidono sui file."""
    mode = bot.get("mode", "paper")
    prefix = (bot.get("env_prefix", "") or "default").rstrip("_")
    symbol = bot["symbol"].replace("/", "_")
    stem = f"{mode}_{prefix}_{symbol}"
    return {
        "state_path": data_dir / f"{stem}_state.json",
        "journal_path": data_dir / f"{stem}_trades.jsonl",
        "health_path": data_dir / f"{stem}_health.json",
    }


# --- applicazione ------------------------------------------------------------

class NodeApp:
    """Ciclo di vita del Node."""

    def __init__(self, config: dict, hub: Optional[MarketDataHub] = None) -> None:
        self.config = config
        self.data_dir = Path(config.get("data_dir", "node_data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        sup = config.get("supervisor", {})
        self.supervisor = ResourceSupervisor(
            ram_critical_pct=float(sup.get("ram_critical_pct", 0.85)),
            ram_throttle_pct=float(sup.get("ram_throttle_pct", 0.70)),
            cpu_critical_pct=float(sup.get("cpu_critical_pct", 0.90)),
            tick_max_factor=float(sup.get("tick_max_factor", 5.0)),
        )

        # SafeModeGuardian (TODO punto 3): livelli CAUTION/SAFE/EMERGENCY
        sm = config.get("safemode", {})
        self.guardian = SafeModeGuardian(
            caution_pct=float(sm.get("caution_pct", 70.0)),
            safe_pct=float(sm.get("safe_pct", 85.0)),
            emergency_pct=float(sm.get("emergency_pct", 95.0)),
            interval_s=float(sm.get("interval_s", 10.0)),
        )
        # flush di emergenza su SQLite WAL (stato + guardian)
        self.sqlite = SqliteStateStore(self.data_dir / "state.sqlite")

        if hub is not None:
            self.hub = hub
        else:
            hub_cfg = config.get("hub", {})
            ws_enabled = bool(hub_cfg.get("ws_enabled", False))
            ex_pro = None
            if ws_enabled:
                try:
                    import ccxt.pro as ccxtpro  # type: ignore
                    ex_pro = ccxtpro.okx({"hostname": "eea.okx.com",
                                          "enableRateLimit": True})
                except Exception as e:  # noqa: BLE001
                    log.warning("ccxt.pro non disponibile (%s) — fallback REST", e)
            self.hub = MarketDataHub(
                ex_rest=build_rest_exchange(config.get("exchange_rest", {"name": "okx"})),
                ex_pro=ex_pro,
                ws_enabled=ws_enabled,
                poll_interval=float(hub_cfg.get("poll_interval", 10)),
                price_ttl=float(hub_cfg.get("price_ttl", 30)),
                ws_max_retries=int(hub_cfg.get("ws_max_retries", 5)),
                ws_retry_base_s=float(hub_cfg.get("ws_retry_base_s", 2.0)),
            )

        self.orchestrator = TradeOrchestrator(supervisor=self.supervisor)
        self.overrides_path = Path(config.get(
            "overrides_file", "config/strategy_overrides.json"))
        self._build_bots()

    def _apply_overrides(self, bot: dict) -> dict:
        """Fonde gli override strategici (strategy_overrides.json) nel bot dict.
        Chiave: 'mode:symbol' oppure il solo symbol. Solo le chiavi whitelist
        vengono accettate; un file corrotto viene ignorato (mai crash)."""
        try:
            if not self.overrides_path.exists():
                return bot
            data = json.loads(self.overrides_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return bot
            key = f"{bot.get('mode', 'paper')}:{bot['symbol']}"
            ov = data.get(key) or data.get(bot["symbol"])
            if not isinstance(ov, dict):
                return bot
            merged = dict(bot)
            merged.update({k: v for k, v in ov.items() if k in _OVERRIDE_KEYS})
            if merged != bot:
                log.info("override strategico [%s]: %s", key, ov)
            return merged
        except Exception as e:  # noqa: BLE001
            log.warning("override strategici ignorati (%s)", e)
            return bot

    def _build_bots(self) -> None:
        for raw_bot in self.config.get("bots", []):
            bot = self._apply_overrides(raw_bot)
            if not bot.get("enabled", True):
                log.info("bot %s disabilitato (config)", bot.get("symbol"))
                continue
            exchange = build_exchange(bot, self.data_dir)
            paths = paths_for(bot, self.data_dir)
            # health_path esplicito (bot live → path v3.3 per dashboard/Zabbix)
            if bot.get("health_path"):
                paths["health_path"] = Path(bot["health_path"])
            # bot_key univoco: mode:env_prefix:symbol (stesso symbol su piu' account)
            bot_key = f"{bot.get('mode', 'paper')}:{bot.get('env_prefix', '') or '-'}:{bot['symbol']}"
            cfg = BotConfig(
                symbol=bot["symbol"],
                capital=float(bot.get("capital", 100)),
                levels=int(bot.get("levels", 3)),
                buy_distance=float(bot.get("buy_distance", 0.01)),
                profit_target=float(bot.get("profit_target", 0.015)),
                tick_interval=float(bot.get("tick_interval", 60)),
                fee=float(bot.get("fee", 0.001 if bot.get("mode", "paper") == "paper" else 0.0)),
                bot_key=bot_key,
                stop_loss_pct=float(bot.get("stop_loss_pct", 0.0)),
                **paths,
            )
            policy = build_policy(bot, exchange)
            risk = RiskManager(
                daily_loss_limit=float(bot.get("daily_loss_limit", 0.05)),
                max_drawdown_limit=float(bot.get("max_drawdown_limit", 0.15)),
            )
            task = BotTask(cfg, exchange, policy, risk,
                           price_source=self._make_price_source(bot["symbol"]),
                           get_equity=self._equity_for(exchange))
            # per i bot paper: il prezzo dell'hub alimenta i fill simulati, e lo
            # stato cash/asset viene ricostruito dal journal al boot (M5)
            if isinstance(exchange, PaperExchange):
                self.hub.subscribe(bot["symbol"], self._paper_price_handler(exchange))
                if task.journal is not None:
                    exchange.rebuild(task.journal.read_all(), cfg.capital)
            # AdaptiveEngine: alimenta il regime ADX/ATR con OHLCV reale (1h)
            on_ohlcv = getattr(task.policy, "on_ohlcv", None)
            if on_ohlcv is not None:
                self.orchestrator.add_ohlcv_source(
                    bot["symbol"], exchange, on_ohlcv)
            self.orchestrator.add_bot(task)
            log.info("bot %s (%s) registrato", bot["symbol"], bot.get("mode", "paper"))

    @staticmethod
    def _equity_for(exchange):
        """Equity reale: paper = cash+asset×prezzo; live = fetch totale (in to_thread)."""
        if isinstance(exchange, PaperExchange):
            return exchange.equity
        return exchange.fetch_total_equity

    def _make_price_source(self, symbol: str):
        def source() -> float:
            return self.hub.price(symbol) or 0.0
        return source

    @staticmethod
    def _paper_price_handler(exchange: PaperExchange):
        async def handler(symbol: str, price: float) -> None:
            exchange.update_price(price)
        return handler

    async def _propagate_safemode(self) -> None:
        """Propaga i flag del guardian ai bot (trading_paused / throttling)."""
        for bot in self.orchestrator.bots.values():
            bot.trading_paused = self.guardian.trading_paused

    async def _on_emergency(self) -> None:
        """EMERGENCY: cancella gli ordini, flush su SQLite WAL, shutdown."""
        log.critical("EMERGENCY SafeMode: cancellazione ordini + flush stato")
        for symbol, bot in self.orchestrator.bots.items():
            try:
                cancel = getattr(bot.ex, "cancel_all", None)
                if cancel:
                    await asyncio.to_thread(cancel, bot.cfg.symbol)
            except Exception as e:  # noqa: BLE001
                log.warning("emergency cancel %s fallito: %s", symbol, e)
            self.sqlite.save(symbol, bot.state.to_dict())
        self.sqlite.save("guardian", {
            "level": "emergency", "ts": time.time(),
            "bots": list(self.orchestrator.bots),
        })
        log.critical("Stato flushato su SQLite; shutdown controllato del Node")
        self._stop.set()

    async def run(self) -> None:
        self._stop = asyncio.Event()
        stop = self._stop
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                # Windows / ambienti senza add_signal_handler
                pass

        await self.hub.start()
        await self.orchestrator.start_all()
        # avvia il SafeModeGuardian (Task in background)
        self.guardian._task = asyncio.create_task(
            self.guardian.run(on_emergency=self._on_emergency,
                              on_change=self._propagate_safemode))
        log.info("Node avviato: %d bot", len(self.orchestrator.bots))
        await stop.wait()
        log.info("Arresto del Node...")
        await self.guardian.stop()
        await self.orchestrator.stop_all()
        await self.hub.stop()
        self.sqlite.close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Denaro Node asincrono")
    parser.add_argument("--config", required=True, help="config JSON del node")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout)

    config = load_node_config(Path(args.config)).to_dict()
    app = NodeApp(config)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
