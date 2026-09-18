#!/usr/bin/env python3
"""scommessa.py — fotografia del progetto scommessa asimmetrica, per la dashboard.

Legge il wallet dal vault, interroga la blockchain di Base (RPC pubblico) e i
prezzi su OKX EEA (endpoint pubblico), e scrive un JSON pulito dove la dashboard
lo puo' servire: web.grivetto.eu/scommessa.json.

Perche' esiste: la dashboard oggi mostra solo la flotta di trading. La scommessa
da 42 EUR e' l'altro progetto e deve essere visibile quanto l'altro — inclusi il
tetto di perdita e il prossimo passo, non solo i saldi.

Uso: python3 tools/scommessa.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

IND = '0x8788D169201cb0D8E5b355e26924c9D3D51ad810'
USDC_BASE = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
RPCS = ('https://base-rpc.publicnode.com', 'https://base.llamarpc.com', 'https://mainnet.base.org')
TETTO_EUR = 42.0


def rpc(method, params):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
    ultimo = 'nessun RPC raggiungibile'
    for url in RPCS:
        try:
            req = urllib.request.Request(url, data=body, headers={
                'Content-Type': 'application/json', 'User-Agent': 'denaro/1.0'})
            return json.loads(urllib.request.urlopen(req, timeout=15).read())
        except Exception as exc:
            ultimo = str(exc)[:80]
    raise RuntimeError(ultimo)


def prezzo(inst):
    url = 'https://eea.okx.com/api/v5/market/ticker?instId=' + inst
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'denaro/1.0'})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return float((d.get('data') or [{}])[0].get('last'))
    except Exception:
        return None


def leggi_vault():
    p = Path(os.path.expanduser('~/airdrop-farm/data/vault_scommessa.json'))
    if not p.is_file():
        return None, None
    try:
        v = json.loads(p.read_text())[0]
        return v.get('address'), v.get('derivation_path')
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.expanduser('~/denaro/denaro/scommessa.json'))
    args = ap.parse_args()

    indirizzo, nota = leggi_vault()
    indirizzo = indirizzo or IND

    dati = {'progetto': 'Scommessa asimmetrica (airdrop farming)', 'ts': time.time(),
            'ts_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'wallet': indirizzo, 'rete': 'Base', 'tetto_perdita_eur': TETTO_EUR,
            'ok': False, 'errore': None}

    try:
        eth = int(rpc('eth_getBalance', [indirizzo, 'latest'])['result'], 16) / 1e18
        data = '0x70a08231' + '0' * 24 + indirizzo[2:].lower()
        usdc = int(rpc('eth_call', [{'to': USDC_BASE, 'data': data}, 'latest'])['result'], 16) / 1e6
        pe = prezzo('ETH-EUR')
        pu = prezzo('USDC-EUR')
        valore = (eth * pe if pe else 0) + (usdc * pu if pu else 0)
        dati.update({'ok': True, 'eth': round(eth, 8), 'usdc': round(usdc, 6),
                     'prezzo_eth_eur': pe, 'prezzo_usdc_eur': pu,
                     'valore_eur': round(valore, 2),
                     'gas_sufficiente': eth > 0.0002,
                     'sopravvivenza_pct': round(100.0 * valore / TETTO_EUR, 1) if TETTO_EUR else None})
    except Exception as exc:
        dati['errore'] = str(exc)[:120]

    dati['fase'] = 'fondazione — wallet finanziato, layer di esecuzione on-chain da scrivere'
    dati['prossimo_passo'] = 'esecuzione on-chain: firma locale, invio, verifica, idempotenza'
    dati['nota'] = nota or 'seed indipendente, nessun HD condiviso'

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(dati, indent=2))
    tmp.replace(out)
    print(json.dumps(dati, indent=2))


if __name__ == '__main__':
    main()
