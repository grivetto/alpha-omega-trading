"""LLM Strategy Optimizer — with Agent-Reach web intelligence."""
from __future__ import annotations
import json, os, re, subprocess, time
from datetime import datetime

from core.config import settings
from core.logger import AgentLogger
from models import ContextState

log = AgentLogger.get("optimizer")

OPTIMIZER_STATE_FILE = "/tmp/llm_optimizer_state.json"

OPTIMIZER_SYSTEM_PROMPT = """You are a crypto grid trading optimizer.
Analyse the market data below, then return ONLY valid JSON:

{"bias":"long|short|none","confidence":0.0-1.0,"grid_action":"narrow|widen|hold","levels_adj":-1|0|1,"reasoning":"short"}

RULES:
- bias=long if RSI<40 or volume spike up
- bias=short if RSI>60 or volume dump
- bias=none if neutral (default)
- grid_action: narrow when trending, widen when ranging
- levels_adj: +1 if trending strongly, -1 if choppy
- ONLY return the JSON, nothing else
"""

def save_state(data: dict):
    data["updated_at"] = datetime.utcnow().isoformat()
    with open(OPTIMIZER_STATE_FILE, "w") as f:
        json.dump(data, f)

class StrategyOptimizer:
    """LLM-driven grid parameter optimizer."""

    def optimize(self, context: ContextState) -> dict:
        log.info("Optimizing %s via LLM..." % context.symbol)
        prompt = self._build_prompt(context)
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "30",
                 settings.llm.endpoint.replace("/v1", "") + "/api/generate",
                 "-d", json.dumps({
                     "model": settings.llm.model,
                     "prompt": OPTIMIZER_SYSTEM_PROMPT + "\n\nData:\n" + prompt,
                     "options": {"num_gpu": 0},
                     "stream": False
                 })],
                capture_output=True, text=True, timeout=35
            )
            if result.stdout:
                data = json.loads(result.stdout)
                raw = data.get("response", "")
                j = re.search(r'\{.*?\}', raw, re.DOTALL)
                if j:
                    sug = json.loads(j.group())
                    save_state({"symbol": context.symbol, **sug})
                    log.info("LLM: bias=%s conf=%.2f action=%s levels=%+d" % (
                        sug.get("bias", "?"), sug.get("confidence", 0),
                        sug.get("grid_action", "?"), sug.get("levels_adj", 0)))
                    return sug
        except Exception as e:
            log.warn("LLM failed: %s" % str(e)[:80])

        fallback = {"bias": "none", "confidence": 0.3, "grid_action": "hold", "levels_adj": 0}
        save_state({"symbol": context.symbol, **fallback})
        return fallback

    def _build_prompt(self, ctx: ContextState) -> str:
        s = ctx.raw_snapshot
        parts = ["%s price=%.2f" % (ctx.symbol, s.price or 0)]
        if s:
            parts += ["spread=%.0fbps" % (s.spread_bps or 0),
                      "vol5m=%.4f" % (s.volatility_5m or 0),
                      "rsi=%.1f" % (s.rsi_14 or 50),
                      "imb=%.3f" % (s.order_book_imbalance or 0),
                      "regime=%s" % ctx.regime.value]
        return " | ".join(parts)
