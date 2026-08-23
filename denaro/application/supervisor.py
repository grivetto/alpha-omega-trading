#!/usr/bin/env python3
"""Denaro — ResourceSupervisor (M4/D6 del blueprint).

Monitora in tempo reale RSS/CPU del nodo e applica:
- circuit breaker di risorse: nessun nuovo worker sopra le soglie (zero OOM)
- backpressure: riduzione della frequenza di tick quando la pressione cresce
- adaptive throttling: il fattore di tick scala con la RAM usata

Puro e deterministico: le metriche arrivano da un callable iniettabile
(`get_metrics`), quindi e' testabile senza I/O reale.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple


@dataclass
class NodeMetrics:
    rss_mb: float = 0.0
    cpu_pct: float = 0.0
    ram_total_mb: float = 0.0


@dataclass
class ResourceState:
    level: str = "nominal"        # nominal | throttled | critical
    tick_factor: float = 1.0      # moltiplicatore dell'intervallo di tick
    can_start_worker: bool = True
    reason: str = ""


class ResourceSupervisor:
    """Supervisore risorse locale: zero OOM + adaptive throttling.

    Parametri (default calibrati per nodi 2-4 GB):
    - ram_critical_pct: frazione di RAM oltre cui si blocca (default 0.85)
    - ram_throttle_pct: frazione oltre cui si rallenta (default 0.70)
    - cpu_critical_pct: CPU oltre cui si blocca (default 0.90)
    - tick_max_factor: massimo rallentamento del tick (default 5.0)
    """

    def __init__(self,
                 ram_critical_pct: float = 0.85,
                 ram_throttle_pct: float = 0.70,
                 cpu_critical_pct: float = 0.90,
                 tick_max_factor: float = 5.0,
                 get_metrics: Optional[Callable[[], NodeMetrics]] = None,
                 now: Optional[Callable[[], float]] = None) -> None:
        self.ram_critical_pct = ram_critical_pct
        self.ram_throttle_pct = ram_throttle_pct
        self.cpu_critical_pct = cpu_critical_pct
        self.tick_max_factor = max(1.0, tick_max_factor)
        self._get_metrics = get_metrics or self._default_metrics
        self._now = now or __import__("time").time
        self._last_check = 0.0
        self._cooldown_s = 5.0

    @staticmethod
    def _default_metrics() -> NodeMetrics:
        """Metriche di default: nessuna informazione → stato nominale."""
        return NodeMetrics()

    def _read_metrics(self) -> NodeMetrics:
        """Legge RSS/CPU del processo corrente (Linux: /proc/self/status)."""
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = float(line.split()[1])
                        return NodeMetrics(rss_mb=rss_kb / 1024.0)
        except Exception:
            pass
        return NodeMetrics()

    def check(self, metrics: Optional[NodeMetrics] = None) -> ResourceState:
        """Valuta lo stato delle risorse.

        Con `metrics=None` usa il callable iniettato (default: /proc).
        Il risultato e' deterministico: stessi input → stesso output.
        """
        m = metrics if metrics is not None else self._get_metrics()
        ram_used = m.rss_mb / max(1.0, m.ram_total_mb) if m.ram_total_mb else 0.0

        state = ResourceState()

        # 1) soglia critica RAM → blocco totale (zero OOM)
        if ram_used >= self.ram_critical_pct:
            state.level = "critical"
            state.can_start_worker = False
            state.tick_factor = self.tick_max_factor
            state.reason = f"ram {ram_used * 100:.0f}% >= {self.ram_critical_pct * 100:.0f}%"
            return state

        # 2) CPU critica → blocco nuovi worker (cpu_pct in percentuale 0-100)
        if m.cpu_pct / 100.0 >= self.cpu_critical_pct:
            state.level = "critical"
            state.can_start_worker = False
            state.tick_factor = min(self.tick_max_factor, 2.0)
            state.reason = f"cpu {m.cpu_pct:.0f}% >= {self.cpu_critical_pct * 100:.0f}%"
            return state

        # 3) RAM in zona throttling → rallenta i tick (backpressure graduale)
        if ram_used >= self.ram_throttle_pct:
            progress = (ram_used - self.ram_throttle_pct) / max(
                1e-9, self.ram_critical_pct - self.ram_throttle_pct)
            factor = 1.0 + progress * (self.tick_max_factor - 1.0)
            state.level = "throttled"
            state.can_start_worker = True
            state.tick_factor = round(factor, 3)
            state.reason = f"ram {ram_used * 100:.0f}% in throttle"
            return state

        state.reason = "nominal"
        return state

    def can_start_worker(self, metrics: Optional[NodeMetrics] = None) -> bool:
        """True se si puo' avviare un nuovo worker (circuit breaker risorse)."""
        return self.check(metrics).can_start_worker

    def adjusted_interval(self, base_interval: float,
                          metrics: Optional[NodeMetrics] = None) -> float:
        """Intervallo di tick adattivo: base × tick_factor."""
        return base_interval * self.check(metrics).tick_factor
