"""Denaro config — env-driven, adaptive defaults, machine-aware.
Auto-loads from environment. No hardcoded secrets."""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from .models import CBConfig, GridConfig, ScalpConfig
from .risk import RiskManager

log = logging.getLogger("denaro.config")


@dataclass
class Config:
    """One config per machine (hostname or env DCKR_HOST)."""

    # ── Exchange ──
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = False

    # ── Pairs ──
    pairs: list[str] = field(default_factory=lambda: ["SOL/USDC", "ADA/USDC", "DOGE/USDC"])

    # ── Allocation ──
    grid_alloc: float = 0.65
    scalp_alloc: float = 0.25
    reserve_alloc: float = 0.10

    # ── Risk ──
    total_capital: float = 200.0

    # ── Strategies ──
    grid: GridConfig = field(default_factory=GridConfig)
    scalp: ScalpConfig = field(default_factory=ScalpConfig)
    cb: CBConfig = field(default_factory=CBConfig)

    # ── Modes ──
    dry_run: bool = False
    shadow_mode: bool = True
    verbose: bool = False

    # ── Timing ──
    loop_interval: float = 1.0
    balance_interval: float = 30.0
    health_interval: float = 5.0
    recv_window: int = 5000
    perf_log_interval: int = 60      # Log perf summary every N cycles

    # ── Compounding ──
    compound_ratio: float = 0.5      # Reinvest 50% of grid profits
    min_compound: float = 1.0        # Min USDC to bother compounding
    auto_boost: bool = True          # Auto-increase sizing during trends

    # ── Resilience ──
    max_restarts: int = 50
    health_timeout: int = 120        # Seconds before declaring unhealthy
    api_retry_delay: float = 1.0     # Initial retry delay (exponential)
    api_max_retries: int = 5

    # ── Risk manager (lazy) ──
    _risk: Optional[RiskManager] = None

    @property
    def risk(self) -> RiskManager:
        if self._risk is None:
            num_pairs = max(len(self.pairs), 1)
            cap_per = self.total_capital / num_pairs
            self._risk = RiskManager(self, total_capital=self.total_capital)
        return self._risk

    # ── Adaptive helpers ──

    def grid_spread(self, atr_pct: float) -> float:
        spread = max(atr_pct * self.grid.spread_atr_mult, self.grid.min_spread)
        return min(spread, self.grid.max_spread)

    def scalp_tp(self, atr_pct: float) -> float:
        return max(atr_pct * self.scalp.tp_atr_mult, self.scalp.min_tp)

    def scalp_sl(self, atr_pct: float) -> float:
        return max(atr_pct * self.scalp.sl_atr_mult, self.scalp.min_sl)


# ── Builder ────────────────────────────────────────────────────────────

def load_config() -> Config:
    """Load config from env vars. Keeps defaults for anything unset."""
    pairs_raw = os.getenv("PAIRS", "SOL/USDC,ADA/USDC,DOGE/USDC")
    pairs = [p.strip() for p in pairs_raw.split(",") if p.strip()]

    shadow = os.getenv("SHADOW_MODE", "1") == "1"
    total_cap = float(os.getenv("TOTAL_CAPITAL", "200.0"))

    cfg = Config(
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
        testnet=os.getenv("TESTNET", "0") == "1",
        pairs=pairs,
        total_capital=total_cap,
        grid_alloc=float(os.getenv("GRID_ALLOC", "0.65")),
        scalp_alloc=float(os.getenv("SCALP_ALLOC", "0.25")),
        reserve_alloc=float(os.getenv("RESERVE_ALLOC", "0.10")),
        dry_run=os.getenv("DRY_RUN", "0") == "1",
        shadow_mode=shadow,
        verbose=os.getenv("VERBOSE", "0") == "1",
        loop_interval=float(os.getenv("LOOP_INTERVAL", "1.0")),
        balance_interval=float(os.getenv("BALANCE_INTERVAL", "30.0")),
        recv_window=int(os.getenv("RECV_WINDOW", "5000")),
        compound_ratio=float(os.getenv("COMPOUND_RATIO", "0.5")),
        auto_boost=os.getenv("AUTO_BOOST", "1") == "1",
        api_retry_delay=float(os.getenv("API_RETRY_DELAY", "1.0")),
    )

    log.info("Config loaded: %d pairs, %.2f USDC total, shadow=%s",
             len(pairs), total_cap, shadow)
    return cfg
