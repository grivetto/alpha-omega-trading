#!/usr/bin/env python3
"""Dump della coda del log di un contesto A0 (item con no >= FROM), mascherato."""
import http.cookiejar
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import Cookie

WIN = "--win" in sys.argv
CTX = sys.argv[sys.argv.index("--ctx") + 1] if "--ctx" in sys.argv else None
FROM = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
BASE = "http://100.76.22.119:50080" if WIN else "http://127.0.0.1:50080"


def env_mc2(key):
    out = subprocess.run(["docker", "exec", "agent-zero", "sh", "-c", "cat /a0/.env"],
                         capture_output=True, text=True, timeout=30).stdout
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def mask(s):
    return re.sub(r"(sk-|or-|AIza|Bearer )[A-Za-z0-9_\-]{8,}", "[REDACTED]", str(s or ""))


cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, data=None, headers=None, form=False):
    h = {"Origin": BASE, "Referer": BASE + "/"}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        with opener.open(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    if not WIN:
        user, password = env_mc2("AUTH_LOGIN"), env_mc2("AUTH_PASSWORD")
        call("GET", "/login")
        if user and password:
            call("POST", "/login", {"username": user, "password": password}, form=True)
    st, raw = call("GET", "/api/csrf_token")
    tok = json.loads(raw)
    token, rid = tok["token"], tok["runtime_id"]
    cj.set_cookie(Cookie(0, "csrf_token_" + rid, token, None, False,
                         "127.0.0.1" if not WIN else "100.76.22.119",
                         False, False, "/", True, False, None, True, None, None, {}))
    st, raw = call("POST", "/api/poll", {"context": CTX, "log_from": 0},
                   headers={"X-CSRF-Token": token})
    d = json.loads(raw.decode(errors="replace"))
    items = [it for it in (d.get("logs") or []) if isinstance(it, dict) and (it.get("no") or 0) >= FROM]
    print("context:", CTX, "| item totali:", len(d.get("logs") or []), "| mostro da no>=", FROM, "|", len(items), "item")
    print("paused:", d.get("paused"), "| log_progress_active:", d.get("log_progress_active"))
    for it in items:
        c = mask(str(it.get("content") or "")).replace("\n", " ")[:280]
        print("[%s] %s | %s" % (it.get("no"), it.get("type"), c))


if __name__ == "__main__":
    main()
