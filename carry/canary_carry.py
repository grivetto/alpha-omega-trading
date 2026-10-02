#!/usr/bin/env python3
"""C1 — Canary carry DOGE (OKX EEA): esecuzione minima spot long + X-Perp short.

Spec pre-dichiarata: docs/16_canary_carry_2026-10-01.md.
Obiettivo = VALIDARE l'esecuzione (fill, slippage, fee, funding, riconciliazione).

Subcomandi (default sola lettura; le scritture richiedono --execute):
  preflight           zero ordini/posizioni, saldi, minimi, bande, spread, fee; piano
  convert --usdc 13   EUR->USDC a limite (taker controllato), attende fill
  open                apre le due gambe (spot buy, poi perp short isolated 1x) [--execute]
  status [--quiet]    stato posizione + funding + riconciliazione + PnL stimato
  close               chiude entrambe le gambe (perp reduceOnly + sell spot) [--execute]

Sicurezze: chiavi mai stampate; LIMIT (mai market); clOrdId idempotenti; poll di fill;
fill parziale gestito e registrato; stato in canary_state.json; eventi in canary_events.jsonl.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt

ENV = Path("/home/marco/denaro/secrets/main_okx.env")
DIR = Path(__file__).resolve().parent
STATE = DIR / "canary_state.json"
EVENTS = DIR / "canary_events.jsonl"

INST = "DOGE-USD_UM_XPERP-310404"
SYM_PER = "DOGE/USD:USD-310404"
SYM_SPOT = "DOGE/USDC"
CT_VAL = 10.0          # DOGE per contratto
Q_SPOT = 110.0         # DOGE lato spot (~10,4 USDC a DOGE≈0,095)
N_CT = 11              # contratti perp (110 DOGE)
LEVER = "1"
MGN = "isolated"


def leggi_env(path):
    d = {}
    for ln in Path(path).read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def client():
    env = leggi_env(ENV)
    return ccxt.okx({
        "apiKey": env["OKX_API_KEY"], "secret": env["OKX_API_SECRET"],
        "password": env["OKX_PASSPHRASE"], "hostname": "eea.okx.com",
        "enableRateLimit": True, "options": {"defaultType": "spot"},
    })


def arg(nome, default=None):
    for i, a in enumerate(sys.argv):
        if a == nome:
            return sys.argv[i + 1]
    return default


def flag(nome):
    return nome in sys.argv


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def evento(ev, **kw):
    riga = {"ts": now_iso(), "event": ev}
    riga.update(kw)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(riga, ensure_ascii=False) + "\n")
    print("EVENT:", ev, json.dumps(kw, ensure_ascii=False)[:220])


def salva_state(st):
    st["updated"] = now_iso()
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def carica_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return None


def attesa_fill(ex, oid, sym, secondi=60, passo=1.5):
    """Poll fino a closed; ritorna (order, esito) con esito in {closed,reprice,partial}."""
    for _ in range(int(secondi / passo)):
        time.sleep(passo)
        try:
            oo = ex.fetch_order(oid, sym)
        except Exception:
            continue
        if oo["status"] == "closed":
            return oo, "closed"
        if oo["status"] == "canceled":
            return oo, "partial"
    try:
        oo = ex.fetch_order(oid, sym)
        return oo, "reprice"
    except Exception:
        return None, "reprice"


def spot_qty(ex):
    try:
        b = ex.fetch_balance()
        return float(b.get("DOGE", {}).get("free") or 0)
    except Exception:
        return 0.0


def posizione(ex):
    for p in ex.privateGetAccountPositions({"instType": "FUTURES"}).get("data", []):
        if p.get("instId") == INST:
            return p
    return None


def preflight(ex):
    ok = True
    ex.load_markets()
    mp, ms = ex.market(SYM_PER), ex.market(SYM_SPOT)
    print("== PREFLIGHT C1 ==")
    ordini = ex.privateGetTradeOrdersPending({}).get("data", [])
    algo = ex.privateGetTradeOrdersAlgoPending({"ordType": "conditional"}).get("data", [])
    pos = ex.privateGetAccountPositions({"instType": "FUTURES"}).get("data", [])
    print(f"ordini pendenti: {len(ordini)} | algo: {len(algo)} | posizioni: {len(pos)}")
    if ordini or algo or pos:
        ok = False
        print("  !! residui presenti: NO-GO")
    tr = ex.privateGetAccountBalance()["data"][0]
    usdc = next((d for d in tr.get("details", []) if d.get("ccy") == "USDC"), None)
    usdc_av = float(usdc.get("availEq") or 0) if usdc else 0.0
    b_doge = spot_qty(ex)
    print(f"USDC trading: {usdc_av:.4f} | DOGE spot in saldo: {b_doge}")
    if usdc_av < 22.5:
        ok = False
        print("  !! USDC < 22.5 (servono ~21.5 per le due gambe + buffer): NO-GO")
    if b_doge > 0.01:
        ok = False
        print("  !! DOGE spot già in saldo (atteso 0): verificare")
    t_p = ex.fetch_ticker(SYM_PER)
    t_s = ex.fetch_ticker(SYM_SPOT)
    spr_p = (float(t_p["ask"]) - float(t_p["bid"])) / float(t_p["last"]) * 1e4
    spr_s = (float(t_s["ask"]) - float(t_s["bid"])) / float(t_s["last"]) * 1e4
    print(f"perp  last {t_p['last']} bid {t_p['bid']} ask {t_p['ask']} | spread {spr_p:.1f} bps")
    print(f"spot  last {t_s['last']} bid {t_s['bid']} ask {t_s['ask']} | spread {spr_s:.1f} bps")
    if spr_p > 50 or spr_s > 50:
        ok = False
        print("  !! spread > 50 bps: NO-GO")
    lim = ex.request("public/price-limit", "public", "GET", {"instId": INST})["data"][0]
    print(f"banda perp: buyLmt {lim.get('buyLmt')} sellLmt {lim.get('sellLmt')}")
    noz = Q_SPOT * float(t_s["last"])
    marg = N_CT * CT_VAL * float(t_p["last"]) 
    print(f"piano: spot {Q_SPOT} DOGE (~{noz:.2f} USDC) + perp short {N_CT} ct (~{marg:.2f} USDC nozionale, margine isolated 1x)")
    fee_f = ex.privateGetAccountTradeFee({"instType": "FUTURES"}).get("data", [{}])[0]
    print(f"fee futures: maker {fee_f.get('maker')} taker {fee_f.get('taker')} (Lv{fee_f.get('level')})")
    fee_s = ex.privateGetAccountTradeFee({"instType": "SPOT"}).get("data", [{}])[0]
    print(f"fee spot: EUR m/t {fee_s.get('maker')}/{fee_s.get('taker')} | USDC m/t {fee_s.get('makerUSDC')}/{fee_s.get('takerUSDC')}")
    print(f"minimi: perp minSz {mp['limits']['amount']['min']} ctVal {mp['contractSize']} | spot min {ms['limits']['amount']['min']}")
    print("PREFLIGHT:", "GO" if ok else "NO-GO")
    return ok


def main():
    ex = client()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "preflight":
        sys.exit(0 if preflight(ex) else 1)

    elif cmd == "convert":
        usdc_amt = float(arg("--usdc", "13"))
        ex.load_markets()
        t = ex.fetch_ticker("USDC/EUR")
        px = ex.price_to_precision("USDC/EUR", float(t["ask"]) * 1.003)
        eur_need = usdc_amt * float(px)
        print(f"convert: compro {usdc_amt} USDC a {px} (ask {t['ask']}) ~ {eur_need:.2f} EUR")
        if not flag("--execute"):
            print("[DRY] nessun ordine inviato")
            return
        cid = "c1cv" + str(int(time.time()))
        o = ex.create_order("USDC/EUR", "limit", "buy", usdc_amt, float(px), params={"clOrdId": cid})
        oo, esito = attesa_fill(ex, o["id"], "USDC/EUR", 45)
        if esito != "closed":
            try:
                ex.cancel_order(o["id"], "USDC/EUR")
            except Exception:
                pass
        print("convert esito:", esito, "filled:", getattr(oo, "get", lambda k, d=None: None)("filled"))
        evento("convert", esito=esito, ordine=o["id"])

    elif cmd == "open":
        st = carica_state()
        if st and st.get("status") == "open":
            sys.exit("stato già 'open' — usare status/close")
        if not preflight(ex):
            sys.exit("preflight NO-GO")
        if not flag("--execute"):
            print("[DRY] open non eseguito")
            return
        # leva 1x isolated (fallback cross registrato)
        try:
            r = ex.privatePostAccountSetLeverage({"instId": INST, "lever": LEVER, "mgnMode": MGN})
            print("set-lever isolated:", r.get("code"))
        except Exception as e:
            print("set-lever isolated ERR:", str(e)[:110], "-> fallback cross")
            ex.privatePostAccountSetLeverage({"instId": INST, "lever": LEVER, "mgnMode": "cross"})
            globals()["MGN"] = "cross"
        # gamba 1: SPOT buy limit
        t_s = ex.fetch_ticker(SYM_SPOT)
        px1 = ex.price_to_precision(SYM_SPOT, float(t_s["ask"]) * 1.002)
        mid1 = float(t_s["last"])
        cid = "c1s" + str(int(time.time()))
        o1 = ex.create_order(SYM_SPOT, "limit", "buy", Q_SPOT, float(px1), params={"clOrdId": cid})
        oo1, es1 = attesa_fill(ex, o1["id"], SYM_SPOT, 60)
        if es1 == "reprice":
            print("spot: reprice")
            oo1_prev = None
            try:
                oo1_prev = ex.fetch_order(o1["id"], SYM_SPOT)
            except Exception:
                pass
            try:
                ex.cancel_order(o1["id"], SYM_SPOT)
            except Exception:
                pass
            filled_prev = float((oo1_prev or {}).get("filled") or 0)
            residuo = Q_SPOT - filled_prev
            t_s = ex.fetch_ticker(SYM_SPOT)
            px1b = ex.price_to_precision(SYM_SPOT, float(t_s["ask"]) * 1.004)
            o1b = ex.create_order(SYM_SPOT, "limit", "buy", residuo, float(px1b), params={"clOrdId": "c1s" + str(int(time.time()) + 1)})
            oo1b, es1 = attesa_fill(ex, o1b["id"], SYM_SPOT, 45)
            if es1 != "closed":
                try:
                    ex.cancel_order(o1b["id"], SYM_SPOT)
                except Exception:
                    pass
        qty_doge = spot_qty(ex)
        avg1 = float((oo1 or {}).get("average") or 0)
        fee1 = float((oo1 or {}).get("fee", {}).get("cost") or 0) if isinstance((oo1 or {}).get("fee"), dict) else 0.0
        fee1_ccy = ((oo1 or {}).get("fee") or {}).get("currency") if isinstance((oo1 or {}).get("fee"), dict) else None
        evento("spot_fill", qty=qty_doge, avg=avg1, fee=fee1, fee_ccy=fee1_ccy, esito=es1, mid_pre=mid1)
        print(f"SPOT: {qty_doge} DOGE @ {avg1} (mid pre {mid1})")
        if qty_doge < 100:
            evento("abort", motivo="spot fill < 100 DOGE", qty=qty_doge)
            sys.exit(f"FILL SPOT INSUFFICIENTE ({qty_doge}) — nessuna gamba perp aperta")
        # gamba 2: PERP short limit
        ct = round(qty_doge / CT_VAL)
        t_p = ex.fetch_ticker(SYM_PER)
        px2 = ex.price_to_precision(SYM_PER, float(t_p["bid"]) * 0.998)
        mid2 = float(t_p["last"])
        o2 = ex.create_order(SYM_PER, "limit", "sell", float(ct), float(px2),
                             params={"tdMode": MGN, "clOrdId": "c1p" + str(int(time.time() + 2))})
        oo2, es2 = attesa_fill(ex, o2["id"], SYM_PER, 60)
        if es2 == "reprice":
            try:
                ex.cancel_order(o2["id"], SYM_PER)
            except Exception:
                pass
            t_p = ex.fetch_ticker(SYM_PER)
            px2b = ex.price_to_precision(SYM_PER, float(t_p["bid"]) * 0.996)
            o2b = ex.create_order(SYM_PER, "limit", "sell", float(ct), float(px2b),
                                  params={"tdMode": MGN, "clOrdId": "c1p" + str(int(time.time() + 3))})
            oo2, es2 = attesa_fill(ex, o2b["id"], SYM_PER, 45)
            if es2 != "closed":
                try:
                    ex.cancel_order(o2b["id"], SYM_PER)
                except Exception:
                    pass
        p = posizione(ex)
        if p and abs(float(p.get("pos") or 0)) >= 1:
            avg2 = float(p.get("avgPx") or 0)
            stato = {
                "status": "open", "ts_open": now_iso(),
                "inst": INST, "symbols": {"perp": SYM_PER, "spot": SYM_SPOT},
                "spot": {"qty": qty_doge, "avg_px": avg1, "fee": fee1, "order": o1["id"], "esito": es1, "mid_pre": mid1},
                "perp": {"ct": abs(float(p.get("pos"))), "avg_px": avg2, "order": o2["id"], "esito": es2, "mid_pre": mid2,
                          "mgnMode": MGN, "lever": LEVER},
                "delta_qty": abs(qty_doge - abs(float(p.get("pos"))) * CT_VAL),
            }
            salva_state(stato)
            evento("open_complete", ct=stato["perp"]["ct"], avg_perp=avg2, qty_spot=qty_doge, delta=stato["delta_qty"])
            print("APERTO:", json.dumps(stato, ensure_ascii=False)[:400])
        else:
            evento("perdita_hedge", motivo="gamba perp assente dopo retry", esito=es2)
            print("!! PERP ASSENTE: chiudo la gamba spot per tornare flat")
            t_s = ex.fetch_ticker(SYM_SPOT)
            pxu = ex.price_to_precision(SYM_SPOT, float(t_s["bid"]) * 0.998)
            try:
                ou = ex.create_order(SYM_SPOT, "limit", "sell", qty_doge, float(pxu), params={"clOrdId": "c1u" + str(int(time.time()))})
                attesa_fill(ex, ou["id"], SYM_SPOT, 45)
                evento("unwind_spot", ordine=ou["id"])
            except Exception as e:
                evento("unwind_spot_ERR", errore=str(e)[:140])
            sys.exit("hedge mancato: spot liquidato per tornare flat (verifica a mano)")

    elif cmd == "status":
        quiet = flag("--quiet")
        st = carica_state() or {"status": "closed"}
        p = posizione(ex)
        b_doge = spot_qty(ex)
        lin = []
        if p:
            pos_ct = abs(float(p.get("pos") or 0))
            upl = float(p.get("upl") or 0)
            fnd = float(p.get("fundingFee") or 0)
            mark = float(p.get("markPx") or 0)
            liq = float(p.get("liqPx") or 0)
            delta = abs(b_doge - pos_ct * CT_VAL)
            mkt = ex.fetch_ticker(SYM_SPOT)
            mid_s = float(mkt["last"])
            spot_avg = float(st.get("spot", {}).get("avg_px") or 0)
            spot_delta = b_doge * (mid_s - spot_avg) if spot_avg else 0.0
            net = spot_delta + upl + fnd
            lin.append(f"C1 DOGE: perp {pos_ct:.0f}ct@ {p.get('avgPx')} mark {mark} upl {upl:+.4f} funding {fnd:+.4f}")
            lin.append(f"   spot {b_doge} DOGE (avg {spot_avg}) mid {mid_s} delta-qty {delta:.2f} liq {liq}")
            lin.append(f"   net stimato (spotΔ+upl+funding) {net:+.4f} USDC")
            an = []
            if delta > 1.0:
                an.append(f"DELTA-QTY {delta:.2f}")
            if mark and pos_ct and float(p.get("avgPx") or 0) and mark > float(p["avgPx"]) * 1.4:
                an.append("MARK +40% -> valutare margine")
            if fnd and abs(fnd) / (pos_ct * CT_VAL * mark) > 0.001:
                an.append(f"funding cum {fnd:.4f}")
            if an:
                lin.append("   ANOMALIE: " + ", ".join(an))
            st.update({"status": "open", "last_pos_ct": pos_ct, "last_mark": mark, "last_upl": upl,
                       "last_funding": fnd, "last_delta": delta, "last_check": now_iso()})
        else:
            lin.append(f"C1 DOGE: nessuna posizione perp | DOGE spot {b_doge}")
            if b_doge > 0.01:
                lin.append("   !! DOGE spot presente senza perp (naked/da chiudere)")
        salva_state(st)
        if quiet:
            print(" | ".join(lin))
        else:
            print("\n".join(lin))

    elif cmd == "close":
        st = carica_state() or {}
        if not flag("--execute"):
            print("[DRY] close non eseguito")
            return
        p = posizione(ex)
        esiti = {}
        if p and abs(float(p.get("pos") or 0)) >= 1:
            ct = abs(float(p.get("pos")))
            t_p = ex.fetch_ticker(SYM_PER)
            px = ex.price_to_precision(SYM_PER, float(t_p["ask"]) * 1.002)
            o = ex.create_order(SYM_PER, "limit", "buy", ct, float(px),
                                params={"tdMode": st.get("perp", {}).get("mgnMode", MGN), "reduceOnly": True,
                                        "clOrdId": "c1x" + str(int(time.time()))})
            oo, es = attesa_fill(ex, o["id"], SYM_PER, 60)
            if es != "closed":
                try:
                    ex.cancel_order(o["id"], SYM_PER)
                except Exception:
                    pass
            esiti["perp"] = es
            evento("close_perp", esito=es, ordine=o["id"])
        b_doge = spot_qty(ex)
        if b_doge > 0.01:
            t_s = ex.fetch_ticker(SYM_SPOT)
            px = ex.price_to_precision(SYM_SPOT, float(t_s["bid"]) * 0.998)
            o = ex.create_order(SYM_SPOT, "limit", "sell", b_doge, float(px), params={"clOrdId": "c1y" + str(int(time.time()))})
            oo, es = attesa_fill(ex, o["id"], SYM_SPOT, 60)
            if es != "closed":
                try:
                    ex.cancel_order(o["id"], SYM_SPOT)
                except Exception:
                    pass
            esiti["spot"] = es
            evento("close_spot", esito=es, ordine=o["id"])
        p2 = posizione(ex)
        b2 = spot_qty(ex)
        st.update({"status": "closed", "ts_close": now_iso(), "esiti": esiti})
        salva_state(st)
        evento("close_complete", pos_residua=bool(p2), doge_residuo=b2, esiti=esiti)
        print("chiuso:", esiti, "| pos residua:", bool(p2), "| DOGE residuo:", b2)

    else:
        sys.exit(f"comando sconosciuto: {cmd}")


if __name__ == "__main__":
    main()
