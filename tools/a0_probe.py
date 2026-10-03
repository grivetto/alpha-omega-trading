#!/usr/bin/env python3
"""Probe raw /api/poll su A0 (debug parametri log_version/log_from). Non stampa contenuti dei log, solo struttura."""
import http.cookiejar
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import Cookie

WIN = "--win" in sys.argv
CTX = sys.argv[sys.argv.index("--ctx") + 1] if "--ctx" in sys.argv else None
BASE = "http://100.76.22.119:50080" if WIN else "http://127.0.0.1:50080"


def env_mc2(key):
    out = subprocess.run(["docker", "exec", "agent-zero", "sh", "-c", "cat /a0/.env"],
                         capture_output=True, text=True, timeout=30).stdout
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


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
            st, _ = call("POST", "/login", {"username": user, "password": password}, form=True)
            print("login:", st)
    st, raw = call("GET", "/api/csrf_token")
    tok = json.loads(raw)
    token, rid = tok["token"], tok["runtime_id"]
    cj.set_cookie(Cookie(0, "csrf_token_" + rid, token, None, False,
                         "127.0.0.1" if not WIN else "100.76.22.119",
                         False, False, "/", True, False, None, True, None, None, {}))
    probes = [
        {"context": CTX, "log_from": 0},
        {"context": CTX, "log_from": 0, "log_version": -1},
        {"context": CTX, "log_from": 0, "log_version": 0},
    ]
    for p in probes:
        st, raw = call("POST", "/api/poll", p, headers={"X-CSRF-Token": token})
        s = raw.decode(errors="replace")
        try:
            d = json.loads(s)
            logs = d.get("logs") or []
            nos = [it.get("no") for it in logs if isinstance(it, dict)]
            print("probe", p, "->", st, "keys:", list(d.keys()), "n_logs:", len(logs),
                  "ultimi no:", nos[-6:] if nos else None, "log_version:", d.get("log_version"))
        except Exception:
            print("probe", p, "->", st, "raw:", s[:200])


if __name__ == "__main__":
    main()
