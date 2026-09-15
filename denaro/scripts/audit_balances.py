#!/usr/bin/env python3
"""Audit saldi reali OKX/Kraken a partire dai file .env. NON stampa mai le chiavi.

Uso:  audit_balances.py /path/.env [etichetta]
Stampa una riga JSON per ogni account trovato nel file .env.
"""
import json
import sys
import ccxt

OKX_PREFIXES = ["", "MARCOSUB1_", "NUVOLASUB1_", "MC2SUB1_", "TRENDSUB_", "TREND_", "MAIN_"]
KRAKEN_PREFIXES = ["", "MARCOSUB1_", "NUVOLASUB1_", "MC2SUB1_", "TRENDSUB_", "TREND_"]


def load_env(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def make_okx(env):
    cfg = {
        "apiKey": env["OKX_API_KEY"],
        "secret": env["OKX_API_SECRET"],
        "password": env.get("OKX_PASSPHRASE", ""),
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    }
    if str(env.get("OKX_EEA", "")).strip() in ("1", "true", "True", "yes"):
        cfg["hostname"] = "eea.okx.com"
    return ccxt.okx(cfg)


def make_kraken(key, secret):
    return ccxt.kraken({"apiKey": key, "secret": secret, "enableRateLimit": True})


def eur_per_stable(ex, cur, cache):
    if cur == "EUR":
        return 1.0
    if cur in cache:
        return cache[cur]
    for pair in ("%s/EUR" % cur, "EUR/%s" % cur):
        try:
            last = ex.fetch_ticker(pair)["last"]
        except Exception:
            continue
        rate = last if pair.endswith("/EUR") else (1.0 / last if last else None)
        if rate:
            cache[cur] = rate
            return rate
    cache[cur] = None
    return None


STABLES = {"USDC", "USDT", "USD", "DAI", "TUSD", "EURT", "BUSD"}


def eur_value(ex, cur, amt, cache):
    if not amt:
        return 0.0
    if cur == "EUR":
        return float(amt)
    candidates = []
    if cur in STABLES:
        candidates.append("%s/EUR" % cur)
    candidates += ["%s/EUR" % cur, "%s/USDC" % cur, "%s/USDT" % cur]
    for pair in candidates:
        try:
            last = ex.fetch_ticker(pair)["last"]
        except Exception:
            continue
        base, quote = pair.split("/")
        if quote == "EUR":
            return float(amt) * float(last)
        rate = eur_per_stable(ex, quote, cache)
        if rate:
            return float(amt) * float(last) * rate
    return None


def audit_exchange(ex, label):
    res = {"account": label, "ok": False, "total_eur": None, "assets": [], "error": ""}
    try:
        bal = ex.fetch_balance()
    except Exception as exc:
        res["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:160])
        print(json.dumps(res), flush=True)
        return res
    cache = {}
    tot = 0.0
    unknown = 0.0
    for cur, info in (bal.get("total") or {}).items():
        amt = info or 0
        if not amt or float(amt) <= 0:
            continue
        v = eur_value(ex, cur, amt, cache)
        if v is None:
            unknown += 1
            res["assets"].append({"cur": cur, "amount": float(amt), "eur": None})
        else:
            tot += v
            if v >= 0.01:
                res["assets"].append({"cur": cur, "amount": float(amt), "eur": round(v, 2)})
    res["ok"] = True
    res["total_eur"] = round(tot, 2)
    res["assets_unpriced"] = unknown
    res["assets"].sort(key=lambda a: -(a["eur"] or 0))
    print(json.dumps(res), flush=True)
    return res


def main():
    env_path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else env_path
    env = load_env(env_path)

    # --- OKX ---
    for pre in OKX_PREFIXES:
        key = env.get("%sOKX_API_KEY" % pre)
        sec = env.get("%sOKX_API_SECRET" % pre)
        if not key or not sec:
            continue
        sub = dict(env)
        sub["OKX_API_KEY"] = key
        sub["OKX_API_SECRET"] = sec
        sub["OKX_PASSPHRASE"] = env.get("%sOKX_PASSPHRASE" % pre) or env.get("OKX_PASSPHRASE", "")
        sub["OKX_EEA"] = env.get("OKX_EEA", "")
        name = "OKX %s%s" % (label, ("/" + pre.rstrip("_")) if pre else "")
        try:
            ex = make_okx(sub)
        except Exception as exc:
            print(json.dumps({"account": name, "ok": False, "error": "init: %s" % exc}), flush=True)
            continue
        audit_exchange(ex, name)
        # prova a elencare i subaccount (funziona solo con chiave master)
        try:
            subs = ex.private_get_users_subaccount_list({})
            names = [s.get("subAcct") for s in (subs.get("data") or [])]
            print(json.dumps({"account": name, "subaccounts": names}), flush=True)
            for sa in names[:20]:
                try:
                    b = ex.private_get_asset_subaccount_balances({"subAcct": sa})
                    print(json.dumps({"account": "%s > sub %s" % (name, sa), "raw": b.get("data")}), flush=True)
                except Exception as exc:
                    print(json.dumps({"account": "%s > sub %s" % (name, sa), "error": str(exc)[:120]}), flush=True)
        except Exception as exc:
            print(json.dumps({"account": name, "subaccounts": None, "subaccounts_error": str(exc)[:120]}), flush=True)

    # --- Kraken ---
    for pre in KRAKEN_PREFIXES:
        key = env.get("%sKRAKEN_API_KEY" % pre)
        sec = env.get("%sKRAKEN_API_SECRET" % pre)
        if not key or not sec:
            continue
        name = "KRAKEN %s%s" % (label, ("/" + pre.rstrip("_")) if pre else "")
        try:
            audit_exchange(make_kraken(key, sec), name)
        except Exception as exc:
            print(json.dumps({"account": name, "ok": False, "error": "init: %s" % exc}), flush=True)


if __name__ == "__main__":
    main()
