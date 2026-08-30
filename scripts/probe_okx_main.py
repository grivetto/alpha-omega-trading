#!/usr/bin/env python3
"""Probe OKX EEA v2: pairing credenziali per BLOCCO (comment-delimited) + prefix.
Identifica MAIN via account/config (uid), saldi reali, specs mercato pubblico,
e test IP-binding POST. NON stampa mai i valori delle chiavi (solo prefix)."""
import re, os
import ccxt

EEA = 'eea.okx.com'
MAIN_UID = '822983321310515677'

def mask(s):
    return (s[:6] + '...') if s else None

# --- parsing a blocchi: ogni commento apre un blocco; chiavi raggruppate per prefix ---
KEY_RE = re.compile(r'^(.*?)_(API_KEY|API_SECRET|SECRET_KEY|PASSPHRASE)$')

def collect_triples(path):
    """Resa lista [{label, k, s, p}] con label = path + block_idx + prefix + header."""
    triples = []
    if not os.path.exists(path):
        return triples
    groups = {}   # (block_idx, prefix) -> {k,s,p,header}
    order = []
    block = 0
    header = None
    for raw in open(path):
        s = raw.strip()
        if not s:
            continue
        if s.startswith('#'):
            header = s.lstrip('#').strip()
            block += 1
            continue
        if '=' not in s:
            continue
        k, v = s.split('=', 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        m = KEY_RE.match(k)
        if not m:
            continue
        prefix, role = m.group(1), m.group(2)
        gkey = (block, prefix)
        if gkey not in groups:
            groups[gkey] = {'k': None, 's': None, 'p': None, 'h': header}
            order.append(gkey)
        if role == 'API_KEY':
            groups[gkey]['k'] = v
        elif role in ('API_SECRET', 'SECRET_KEY'):
            groups[gkey]['s'] = v
        elif role == 'PASSPHRASE':
            groups[gkey]['p'] = v
    base = os.path.basename(path)
    for (block, prefix) in order:
        g = groups[(block, prefix)]
        if g['k']:
            triples.append({'label': f"{base}[b{block}:{prefix}] {g['h']}",
                            'k': g['k'], 's': g['s'], 'p': g['p']})
    return triples

def get_uid(ex):
    """Prova account/config e fallback fetch_accounts."""
    try:
        r = ex.privateGetAccountConfig()
        data = r.get('data', []) or []
        if data:
            d = data[0]
            return d.get('uid'), d.get('mainUid'), d.get('acctLv')
    except Exception:
        pass
    try:
        accts = ex.fetch_accounts()
        if accts:
            a = accts[0]
            return a.get('id') or a.get('info', {}).get('uid'), None, None
    except Exception:
        pass
    return None, None, None

def main():
    paths = [
        '/home/sergio/.denaro_vault/keys_master.env',
        '/home/sergio/denaro/.env',
        '/home/sergio/denaro_node_app/.env',
        '/home/sergio/alpha-omega-trading/.env',
    ]
    triples = []
    for p in paths:
        triples.extend(collect_triples(p))

    # dedup per apiKey
    seen, uniq = set(), []
    for t in triples:
        if t['k'] and t['k'] not in seen:
            seen.add(t['k']); uniq.append(t)

    print(f"== {len(uniq)} credenziali OKX uniche (per blocco/prefix) su {EEA} ==\n")
    main_item = None
    for item in uniq:
        label, ak, sk, pw = item['label'], item['k'], item['s'], item['p']
        if not sk or not pw:
            print(f"[{label}] key={mask(ak)} -> INCOMPLETO (secret/passphrase mancante), skip")
            continue
        try:
            ex = ccxt.okx({'apiKey': ak, 'secret': sk, 'password': pw,
                           'hostname': EEA, 'enableRateLimit': True,
                           'options': {'defaultType': 'spot'}})
            uid, mainuid, lvl = get_uid(ex)
            bal = ex.fetch_balance()
            nz = {c: b for c, b in bal.get('total', {}).items() if b}
            nz_s = ', '.join(f'{c}={v:.6g}' for c, v in sorted(nz.items()))
            tag = '*** MAIN ***' if (uid and str(uid) == MAIN_UID) else ''
            print(f"[{label}]")
            print(f"    key={mask(ak)} uid={uid} mainUid={mainuid} acctLv={lvl} {tag}")
            print(f"    saldi non-zero: {nz_s or '(zero)'}")
            if tag and not main_item:
                main_item = item
        except Exception as e:
            print(f"[{label}] key={mask(ak)} -> ERROR: {str(e)[:160]}")

    # --- specs mercato pubblico (no auth) + ticker ---
    print("\n== MARKET SPECS PUBBLICO (eea.okx.com, no auth) ==")
    pub = ccxt.okx({'hostname': EEA, 'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}})
    try:
        r = pub.publicGetPublicInstruments({'instType': 'SPOT'})
        insts = r.get('data', [])
        want = {'ADA-EUR', 'DOGE-EUR', 'SOL-EUR', 'ETH-EUR', 'DOGE-USDT', 'ADA-USDT'}
        for d in insts:
            iid = d.get('instId')
            if iid in want:
                print(f"{iid}: state={d.get('state')} minSz={d.get('minSz')} "
                      f"lotSz={d.get('lotSz')} tickSz={d.get('tickSz')} "
                      f"minNotional={d.get('minNotional')} base={d.get('baseCcy')} "
                      f"quote={d.get('quoteCcy')} qtyU={d.get('ctVal')}")
    except Exception as e:
        print(f"instruments err: {str(e)[:160]}")
    for iid in ('ADA-EUR', 'DOGE-EUR', 'SOL-EUR'):
        try:
            t = pub.publicGetMarketTicker({'instId': iid})
            d = (t.get('data') or [{}])[0]
            print(f"  ticker {iid}: last={d.get('last')} bid={d.get('bidPx')} ask={d.get('askPx')}")
        except Exception as e:
            print(f"  ticker {iid} err: {str(e)[:100]}")

    # --- IP-binding POST test sulla chiave MAIN (se trovata) ---
    if main_item:
        label, ak, sk, pw = main_item['label'], main_item['k'], main_item['s'], main_item['p']
        print(f"\n== IP-BINDING POST TEST su {label} ==")
        ex = ccxt.okx({'apiKey': ak, 'secret': sk, 'password': pw,
                       'hostname': EEA, 'enableRateLimit': True,
                       'options': {'defaultType': 'spot'}})
        try:
            # POST privato raw: senza load_markets (che trascina fetch_currencies privato).
            ex.privatePostTradeCancelOrder({'instId': 'BTC-USDT', 'ordId': 'probe-ipbinding-000'})
            print("POST OK: nessun errore binding (cancel dummy passato)")
        except Exception as e:
            msg = str(e)
            print(f"POST: {msg[:200]}")
            if '50035' in msg or 'bound' in msg.lower() or 'IP' in msg:
                print("  >> IP-BINDING BLOCCA POST da mc2 -> serve MARCODG1 o rebind UI.")
            elif 'not exist' in msg.lower() or '51400' in msg or 'does not exist' in msg.lower() or '51000' in msg:
                print("  >> POST raggiunge OKX (binding OK): 'order not found' atteso, chiave operativa.")
            elif '50113' in msg:
                print("  >> Invalid Sign: credenziali stale/scorrette, NON binding.")
            else:
                print("  >> esito ambiguo: interpretare codice sopra.")
    else:
        print("\n== MAIN NON IDENTIFICATA tra le credenziali testate ==")

if __name__ == '__main__':
    main()
