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
    )


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
        self._build_bots()

    def _build_bots(self) -> None:
        for bot in self.config.get("bots", []):
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
                **paths,
            )
            policy = GridPolicy(build_grid_params(bot))
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
