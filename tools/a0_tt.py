#!/usr/bin/env python3
"""Client _time_travel per A0: workspaces | list | preview | revert. Masked."""
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
BASE = "http://100.76.22.119:50080" if WIN else "http://127.0.0.1:50080"
MODE = "workspaces"
for m in ("workspaces", "list", "preview", "revert", "travel"):
    if f"--{m}" in sys.argv:
        MODE = m


def arg(name, default=""):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


CTX = arg("--ctx")
WS = arg("--ws")
COMMIT = arg("--commit")
FILE = arg("--file")
DIRECTION = arg("--direction", "backward")


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

    if MODE == "workspaces":
        path, payload = "/api/plugins/_time_travel/history_workspaces", {"context_id": CTX}
    elif MODE == "list":
        path, payload = "/api/plugins/_time_travel/history_list", {"context_id": CTX, "workspace_id": WS, "file_filter": FILE, "limit": 200}
    elif MODE == "preview":
        path, payload = "/api/plugins/_time_travel/history_preview", {"context_id": CTX, "workspace_id": WS, "commit_hash": COMMIT, "file": FILE}
    elif MODE == "travel":
        path, payload = "/api/plugins/_time_travel/history_travel", {"context_id": CTX, "workspace_id": WS, "commit_hash": COMMIT, "direction": DIRECTION}
    else:
        path, payload = "/api/plugins/_time_travel/history_revert", {"context_id": CTX, "workspace_id": WS, "commit_hash": COMMIT}

    st, raw = call("POST", path, payload, headers={"X-CSRF-Token": token})
    txt = raw.decode(errors="replace")
    print("HTTP", st)
    try:
        d = json.loads(txt)
        if "--compact" in sys.argv and MODE == "list":
            print("current:", str(d.get("current_hash") or "")[:12], "| present:", (d.get("present") or {}).get("files_count"))
            for c in (d.get("commits") or []):
                files = ", ".join(f"{f.get('path')}(+{f.get('additions')}/-{f.get('deletions')})" for f in (c.get("files") or []))
                print("%s %s | %s | %s || %s" % (c.get("short_hash"), c.get("timestamp", ""), c.get("message", ""),
                                                 (c.get("metadata") or {}).get("trigger", ""), files[:220]))
            return
        out = json.dumps(d, ensure_ascii=False, indent=1)
        print(mask(out)[:2600])
    except Exception:
        print(mask(txt)[:1200])


if __name__ == "__main__":
    main()
