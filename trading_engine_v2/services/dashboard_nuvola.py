#!/usr/bin/env python3
"""Denaro Dashboard v2 — FastAPI server running on Nuvola."""
from __future__ import annotations
import asyncio, json, time, os
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from starlette.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).resolve().parents[1]
TEMPLATES = BASE / "templates"
app = FastAPI(title="Denaro Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Read API keys from env files on the machine
def load_keys(filepath):
    keys = {}
    try:
        with open(filepath) as f:
            for line in f:
                if line.startswith("BINANCE_API_KEY="):
                    keys["k"] = line.split("=", 1)[1].strip()
                elif line.startswith("BINANCE_API_SECRET="):
                    keys["s"] = line.split("=", 1)[1].strip()
    except:
        pass
    return keys

# Sub-account keys (from local .env files)
NUVOLA_KEYS = load_keys(BASE / ".env")
MC2_KEYS = {"k": "G73HP5WHS5bQNwJTFAoVMbdamgVU3JkG79yDJ2Pt199abLpDV4LjOrEAmQoC9vew",
            "s": "nIV5sWI11K9StdPPopESTU2OzAjRBVlAhj5Zi9B2SxDrcuCjgZJZDJJ759D6je7b"}
MARCODG1_KEYS = {"k": "tKZNn5nFUhoCeMXaQ04ew7CvBMgpe3Bc5h21f7mxBq5yZktgEwUK0SY0k5NGqIEm",
                 "s": "rBfBtrou1Gc4ZEXL2wuEqz9UVhW9ouy4XqKM7NkHyUHDFV5CBlrbQkPQB23QjUCL"}
MAIN_KEYS = {"k": "EnnVpIeAiXz3BPeOWxfGvacUd7iLkY0lqPI09FloYkGhrotNmSIUMlgYp4X6Hne5",
             "s": "vEKYwZO2uC0nLEMpbdaCrCp9QoVabvWuEuZW2EAPCk97jd7ZZhBVYnhpzyg9CMm2"}

pnl_history = []

async def get_balance(creds, timeout=10):
    import ccxt.async_support as ccxt
    if not creds.get("k"):
        return {}
    try:
        ex = ccxt.binance({"apiKey": creds["k"], "secret": creds["s"],
                           "enableRateLimit": True, "options": {"defaultType": "spot"}})
        b = await asyncio.wait_for(ex.fetch_balance(), timeout=timeout)
        await ex.close()
        return b.get("free", {})
    except Exception as e:
        return {"error": str(e)[:80]}

async def get_ticker(symbol):
    import ccxt.async_support as ccxt
    try:
        ex = ccxt.binance({"enableRateLimit": True})
        t = await asyncio.wait_for(ex.fetch_ticker(symbol), timeout=5)
        await ex.close()
        return t["last"]
    except:
        return 0

async def account_value(bal):
    if not bal or "error" in bal:
        return 0
    val = 0
    for asset, amt in bal.items():
        if amt <= 0:
            continue
        if asset == "USDC":
            val += amt
        elif asset in ("SOL", "ADA", "BTC", "ETH"):
            price = await get_ticker(f"{asset}/USDC")
            val += amt * price
    return val

@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES / "index.html").read_text()
    return HTMLResponse(content=html)

@app.get("/api/state")
async def api_state():
    tasks = {
        "nuvola": NUVOLA_KEYS,
        "mc2": MC2_KEYS,
        "marcodg1": MARCODG1_KEYS,
        "main": MAIN_KEYS,
    }
    results = {}
    total = 0.0

    for name, creds in tasks.items():
        bal = await get_balance(creds, timeout=8)
        val = await account_value(bal)
        results[name] = {"balance": {k: round(v, 6) for k, v in bal.items() if isinstance(v, (int, float)) and v > 0},
                         "value_usd": round(val, 2)}
        total += val

    return {
        "accounts": results,
        "total_capital_usd": round(total, 2),
        "trading_capital_usd": round(results.get("main", {}).get("value_usd", 0) +
                                       results.get("nuvola", {}).get("value_usd", 0) +
                                       results.get("mc2", {}).get("value_usd", 0) +
                                       results.get("marcodg1", {}).get("value_usd", 0), 2),
        "pnl_history": pnl_history[-50:],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8900)
