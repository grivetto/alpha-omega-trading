#!/usr/bin/env python3
"""Denaro Dashboard v2 — Standalone FastAPI server."""
from __future__ import annotations
import asyncio, json, time
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).resolve().parents[1]
TEMPLATES = BASE / "templates"
app = FastAPI(title="Denaro Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Hardcoded sub-account API keys
API_KEYS = {
    "mc2": {"k": "G73HP5WHS5bQNwJTFAoVMbdamgVU3JkG79yDJ2Pt199abLpDV4LjOrEAmQoC9vew", "s": "nIV5sWI11K9StdPPopESTU2OzAjRBVlAhj5Zi9B2SxDrcuCjgZJZDJJ759D6je7b"},
}

MAIN_KEY = {"k": "EnnVpIeAiXz3BPeOWxfGvacUd7iLkY0lqPI09FloYkGhrotNmSIUMlgYp4X6Hne5", "s": "vEKYwZO2uC0nLEMpbdaCrCp9QoVabvWuEuZW2EAPCk97jd7ZZhBVYnhpzyg9CMm2"}

pnl_history = []
trade_history = []

async def get_balance(api_key, secret, timeout=10):
    import ccxt.async_support as ccxt
    try:
        ex = ccxt.binance({"apiKey": api_key, "secret": secret, "enableRateLimit": True, "options": {"defaultType": "spot"}})
        b = await asyncio.wait_for(ex.fetch_balance(), timeout=timeout)
        await ex.close()
        return b.get("free", {})
    except Exception as e:
        return {"error": str(e)[:60]}

async def get_usd_value(asset, amount):
    if asset == "USDC":
        return amount
    try:
        import ccxt.async_support as ccxt
        ex = ccxt.binance({"enableRateLimit": True})
        t = await asyncio.wait_for(ex.fetch_ticker(f"{asset}/USDC"), timeout=5)
        await ex.close()
        return amount * t["last"]
    except:
        return 0

@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES / "index.html").read_text()
    return HTMLResponse(content=html)

@app.get("/api/state")
async def api_state():
    balances = {}
    total_usd = 0.0

    for name, creds in API_KEYS.items():
        bal = await get_balance(creds["k"], creds["s"], timeout=8)
        if "error" in bal:
            balances[name] = {"error": bal["error"], "usdc": 0, "value_usd": 0}
        else:
            usdc = bal.get("USDC", 0)
            sol = bal.get("SOL", 0)
            sol_val = await get_usd_value("SOL", sol)
            val = usdc + sol_val
            balances[name] = {"usdc": usdc, "sol": sol, "value_usd": round(val, 2)}
            total_usd += val

    # MAIN balance
    main_bal = await get_balance(MAIN_KEY["k"], MAIN_KEY["s"], timeout=8)
    main = {"usdc": 0, "btc": 0, "value_usd": 0}
    if "error" not in main_bal:
        usdc = main_bal.get("USDC", 0)
        btc = main_bal.get("BTC", 0)
        btc_val = await get_usd_value("BTC", btc)
        main = {"usdc": usdc, "btc": btc, "value_usd": round(usdc + btc_val, 2)}
        total_usd += main["value_usd"]

    return {
        "main": main,
        "sub_accounts": balances,
        "total_capital_usd": round(total_usd, 2),
        "trading_capital_usd": round(sum(v.get("value_usd", 0) for v in balances.values()), 2),
        "pnl_history": pnl_history[-50:],
        "recent_trades": trade_history[-20:],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8900)
