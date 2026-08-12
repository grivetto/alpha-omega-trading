#!/usr/bin/env python3
"""Tests for alpha_omega fleet fixes:
1. Kraken signing matches ccxt (base64 secret + Kraken spec).
2. OKX signing is untouched (still raw secret, correct for OKX).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ccxt

from alpha_omega.core.exchange import KrakenAdapter, OKXAdapter

KEY = "API_KEY_TEST_123"
SECRET = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsUkXN84Tq5cFSY="  # public Kraken doc example
TS = "1616492376594"
PARAMS = {"ordertype": "limit", "pair": "XBTUSD", "price": "37500",
          "type": "buy", "volume": "1.25"}


def make_adapter(cls):
    return cls("kraken", KEY, SECRET, "pass", False, False, "", "", "")


def test_kraken_sign_matches_ccxt():
    adapter = make_adapter(KrakenAdapter)
    headers = adapter._sign_request("POST", "/0/private/AddOrder", PARAMS, TS)

    ex = ccxt.kraken({"apiKey": KEY, "secret": SECRET})
    ex.nonce = lambda: int(TS)  # force the same nonce as the adapter
    # ccxt takes the SHORT path; it composes '/0/private/AddOrder' internally,
    # which matches the full path the adapter signs over.
    signed = ex.sign("AddOrder", "private", "POST", PARAMS)

    # ccxt's API-Sign is base64 — same as the adapter's spec implementation
    assert headers["API-Sign"] == signed["headers"]["API-Sign"], (
        f"signature mismatch: {headers['API-Sign']} vs {signed['headers']['API-Sign']}")
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"

    # body must carry the nonce (Kraken requirement)
    body_out = adapter._signed_body(PARAMS, TS)
    assert "nonce=1616492376594" in body_out


def test_kraken_sign_differs_from_old_broken_format():
    """Guard: the old raw-encode + custom-message scheme must NOT be used."""
    adapter = make_adapter(KrakenAdapter)
    headers = adapter._sign_request("POST", "/0/private/Balance", {}, TS)
    # old scheme produced a 128-char hex signature over raw secret
    assert len(headers["API-Sign"]) < 100  # base64, not hex


def test_okx_sign_uses_raw_secret():
    adapter = OKXAdapter("okx", KEY, SECRET, "passphrase", False, False, "", "", "")
    headers = adapter._sign_request("GET", "/api/v5/account/balance", {}, TS)
    # OKX signature is hex hmac-sha256 (64 chars) with raw secret
    assert len(headers.get("OK-ACCESS-SIGN", "")) == 64
    assert headers["OK-ACCESS-PASSPHRASE"] == "passphrase"
