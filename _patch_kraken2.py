#!/usr/bin/env python3
"""Align Kraken signing with the exact ccxt algorithm (verified live):
   signature = b64(hmac_sha512(url + sha256(nonce + body), b64(secret)))
"""
from pathlib import Path

path = Path("alpha_omega/core/exchange.py")
raw = path.read_bytes()
crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n")

old = """        \"\"\"Kraken spec: base64(hmac_sha512(sha256(nonce + postdata), b64(secret))).\"\"\"
        post_data = self._signed_body(params, timestamp)
        try:
            secret_bytes = base64.b64decode(self.api_secret, validate=True)
        except Exception:
            secret_bytes = self.api_secret.encode()
        sha = hashlib.sha256((timestamp + post_data).encode()).digest()
        signature = base64.b64encode(
            hmac.new(secret_bytes, sha, hashlib.sha512).digest()
        ).decode()"""

new = """        \"\"\"Kraken (ccxt-compatible, verified live):
        b64(hmac_sha512(url + sha256(nonce + body), b64(secret))).\"\"\"
        post_data = self._signed_body(params, timestamp)
        try:
            secret_bytes = base64.b64decode(self.api_secret, validate=True)
        except Exception:
            secret_bytes = self.api_secret.encode()
        hash256 = hashlib.sha256((timestamp + post_data).encode()).digest()
        binhash = path.encode() + hash256
        signature = base64.b64encode(
            hmac.new(secret_bytes, binhash, hashlib.sha512).digest()
        ).decode()"""

assert text.count(old) == 1, f"anchor not found ({text.count(old)})"
text = text.replace(old, new)

out = text.replace("\n", "\r\n") if crlf else text
path.write_bytes(out.encode("utf-8"))
print("PATCH OK (crlf=%s)" % crlf)
