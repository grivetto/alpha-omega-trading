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

from denaro.application.orchestrator import BotConfig, BotTask, TradeOrchestrator
from denaro.application.supervisor import ResourceSupervisor
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.exchanges.paper import PaperExchange
from denaro.infrastructure.market_data import MarketDataHub

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
    mode = bot.get("mode", "paper")
    symbol = bot["symbol"]
    if mode == "paper":
        return PaperExchange(symbol, capital=float(bot.get("capital", 100)),
                             quote=bot.get("quote", "EUR"))
    if mode == "okx":
        from denaro.infrastructure.exchanges.okx import OKXAdapter
        return OKXAdapter(
            api_key=bot["api_key"], secret=bot["secret"],
            passphrase=bot["passphrase"])
    raise ValueError(f"modalita' bot sconosciuta: {mode}")


def paths_for(bot: dict, data_dir: Path) -> Dict[str, Path]:
    symbol = bot["symbol"].replace("/", "_")
    return {
        "state_path": data_dir / f"{symbol}_state.json",
        "journal_path": data_dir / f"{symbol}_trades.jsonl",
        "health_path": data_dir / f"{symbol}_health.json",
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

        if hub is not None:
            self.hub = hub
        else:
            hub_cfg = config.get("hub", {})
            self.hub = MarketDataHub(
                ex_rest=build_rest_exchange(config.get("exchange_rest", {"name": "okx"})),
                ws_enabled=bool(hub_cfg.get("ws_enabled", False)),
                poll_interval=float(hub_cfg.get("poll_interval", 10)),
                price_ttl=float(hub_cfg.get("price_ttl", 30)),
            )

        self.orchestrator = TradeOrchestrator(supervisor=self.supervisor)
        self._build_bots()

    def _build_bots(self) -> None:
        for bot in self.config.get("bots", []):
            exchange = build_exchange(bot, self.data_dir)
            paths = paths_for(bot, self.data_dir)
            cfg = BotConfig(
                symbol=bot["symbol"],
                capital=float(bot.get("capital", 100)),
                levels=int(bot.get("levels", 3)),
                buy_distance=float(bot.get("buy_distance", 0.01)),
                profit_target=float(bot.get("profit_target", 0.015)),
                tick_interval=float(bot.get("tick_interval", 60)),
                fee=float(bot.get("fee", 0.001 if bot.get("mode", "paper") == "paper" else 0.0)),
                **paths,
            )
            policy = GridPolicy(build_grid_params(bot))
            risk = RiskManager(
                daily_loss_limit=float(bot.get("daily_loss_limit", 0.05)),
                max_drawdown_limit=float(bot.get("max_drawdown_limit", 0.15)),
            )
            task = BotTask(cfg, exchange, policy, risk,
                           price_source=self._make_price_source(bot["symbol"]))
            # per i bot paper il prezzo dell'hub alimenta anche i fill simulati
            if isinstance(exchange, PaperExchange):
                self.hub.subscribe(bot["symbol"], self._paper_price_handler(exchange))
            self.orchestrator.add_bot(task)
            log.info("bot %s (%s) registrato", bot["symbol"], bot.get("mode", "paper"))

    def _make_price_source(self, symbol: str):
        def source() -> float:
            return self.hub.price(symbol) or 0.0
        return source

    @staticmethod
    def _paper_price_handler(exchange: PaperExchange):
        async def handler(symbol: str, price: float) -> None:
            exchange.update_price(price)
        return handler

    async def run(self) -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                # Windows / ambienti senza add_signal_handler
                pass

        await self.hub.start()
        await self.orchestrator.start_all()
        log.info("Node avviato: %d bot", len(self.orchestrator.bots))
        await stop.wait()
        log.info("Arresto del Node...")
        await self.orchestrator.stop_all()
        await self.hub.stop()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Denaro Node asincrono")
    parser.add_argument("--config", required=True, help="config JSON del node")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout)

    config = load_config(Path(args.config))
    app = NodeApp(config)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
