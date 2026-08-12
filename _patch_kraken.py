#!/usr/bin/env python3
"""Patch alpha_omega/core/exchange.py: correct Kraken REST signing.

Kraken private API requires:
  API-Sign = base64(hmac_sha512(sha256(nonce + postdata), base64(secret)))
with a form-urlencoded body that includes the nonce.

The adapter previously signed a made-up message
(ts + method + path + sha256hex(post)) over a JSON body, which Kraken
rejects with EAPI:Invalid key -> empty balances -> bots frozen by the
daily-loss guard. This patch:

  1. adds a `_signed_body` hook on the base adapter (None => JSON body),
  2. rewrites KrakenAdapter._sign_request per the Kraken spec and adds
     `_signed_body` (urlencoded with nonce),
  3. makes the base `_request` send `data=signed_body` when the hook
     returns a string.

Line endings are preserved so the git diff stays minimal.
"""
from pathlib import Path

path = Path("alpha_omega/core/exchange.py")
raw = path.read_bytes()
crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n")

# 1) Base class: add _signed_body hook next to the abstract _sign_request
base_hook = """    @abstractmethod
    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        \"\"\"Generate signed headers for authenticated request.\"\"\"
        pass
"""
base_hook_new = base_hook + """
    def _signed_body(self, params: Dict, timestamp: str) -> Optional[str]:
        \"\"\"Body encoding for signed requests. None => JSON body (default).\"\"\"
        return None
"""
assert text.count(base_hook) == 1, "base hook anchor not found"
text = text.replace(base_hook, base_hook_new)

# 2) Base _request: honor signed_body
old_request = """        if signed:
            # Use UTC timestamp for OKX (required for auth)
            import datetime
            timestamp = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000))
            headers.update(self._sign_request(method, path, params or {}, timestamp))
        
        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                async with session.post(url, json=params, headers=headers) as resp:
                    return await self._handle_response(resp)"""
new_request = """        signed_body = None
        if signed:
            # Use UTC timestamp (OKX requires UTC ms; Kraken uses it as nonce)
            import datetime
            timestamp = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000))
            headers.update(self._sign_request(method, path, params or {}, timestamp))
            signed_body = self._signed_body(params or {}, timestamp)
        
        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                kwargs = {"data": signed_body} if signed_body is not None else {"json": params}
                async with session.post(url, headers=headers, **kwargs) as resp:
                    return await self._handle_response(resp)"""
assert text.count(old_request) == 1, "request block anchor not found"
text = text.replace(old_request, new_request)

# 3) KrakenAdapter._sign_request: full spec implementation + _signed_body
old_kraken = """    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        post_data = urllib.parse.urlencode(params) if params else ""
        message = timestamp + method.upper() + path + hashlib.sha256(post_data.encode()).hexdigest()
        # Kraken API secrets are base64-encoded: decode before HMAC-SHA512
        # (matches ccxt behavior - raw-encoding yields EAPI:Invalid key and
        #  empty balances, freezing the bots via the daily-loss guard).
        try:
            secret_bytes = base64.b64decode(self.api_secret, validate=True)
        except Exception:
            secret_bytes = self.api_secret.encode()
        signature = hmac.new(
            secret_bytes,
            message.encode(),
            hashlib.sha512
        ).hexdigest()
        return {
            "API-Key": self.api_key,
            "API-Sign": signature,
        }"""
new_kraken = """    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        \"\"\"Kraken spec: base64(hmac_sha512(sha256(nonce + postdata), b64(secret))).\"\"\"
        post_data = self._signed_body(params, timestamp)
        try:
            secret_bytes = base64.b64decode(self.api_secret, validate=True)
        except Exception:
            secret_bytes = self.api_secret.encode()
        sha = hashlib.sha256((timestamp + post_data).encode()).digest()
        signature = base64.b64encode(
            hmac.new(secret_bytes, sha, hashlib.sha512).digest()
        ).decode()
        return {
            "API-Key": self.api_key,
            "API-Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _signed_body(self, params: Dict, timestamp: str) -> str:
        # Kraken private calls require a form-encoded body carrying the nonce
        return urllib.parse.urlencode({**params, "nonce": timestamp})"""
assert text.count(old_kraken) == 1, "kraken sign block anchor not found"
text = text.replace(old_kraken, new_kraken)

out = text.replace("\n", "\r\n") if crlf else text
path.write_bytes(out.encode("utf-8"))
print("PATCH OK (crlf=%s)" % crlf)
