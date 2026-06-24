#!/usr/bin/env python3
"""Universal Transfer: move USDC from sub-accounts to mc2orion.
Run from MC2 (whitelisted IP)."""
import requests, hmac, hashlib, time, json, urllib.parse, sys

API_KEY = "hvVbfZyvwVKwqjKqz5u03kC7VX9beybhm0xqDnJTem8u2nlKeNaJ0plqG4aI0rWJ"
SECRET = "hnUfoiHQEKf5eU6J5EQ6SNPzEM7HHJHY3bSUtbQYaTJnRiDxCaQUknn95rdNE7R4"

FROM_EMAILS = {
    "nuvola": "nuvolatrading_virtual@2lyv5fu2noemail.com",
    "marcodg1": "marcodg1marcosol_virtual@pwomuqu6noemail.com",
}
TO_EMAIL = "mc2orion_virtual@85origvknoemail.com"

def signed_post(path, params=None):
    if params is None:
        params = {}
    params["timestamp"] = str(int(time.time() * 1000))
    query = urllib.parse.urlencode(params)
    sig = hmac.new(SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com{path}?{query}&signature={sig}"
    r = requests.post(url, headers={"X-MBX-APIKEY": API_KEY}, timeout=15)
    return r.json()

source = sys.argv[1] if len(sys.argv) > 1 else "nuvola"
amount = float(sys.argv[2]) if len(sys.argv) > 2 else 49.0

from_email = FROM_EMAILS.get(source, FROM_EMAILS["nuvola"])
print(f"Transferring ${amount:.2f} USDC from {source} ({from_email}) to mc2orion...")

r = signed_post("/sapi/v1/sub-account/universalTransfer", {
    "fromEmail": from_email,
    "toEmail": TO_EMAIL,
    "fromAccountType": "SPOT",
    "toAccountType": "SPOT",
    "asset": "USDC",
    "amount": amount,
})

print(json.dumps(r, indent=2))
if r.get("tranId"):
    print(f"SUCCESS: tranId={r['tranId']}")
