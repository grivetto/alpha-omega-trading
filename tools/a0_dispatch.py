#!/usr/bin/env python3
"""Dispatch verso A0 (v2.13): contesto NUOVO + kickoff + watch breve.

Uso:
  python3 a0_dispatch.py [--win] <path-assoluto-brief-nel-workspace-A0> [minuti-watch]
Target:
  default = A0-mc2 (http://127.0.0.1:50080; credenziali dal dotenv del container via docker exec)
  --win   = A0-win (http://100.76.22.119:50080; login libera, niente docker)
Non stampa mai segreti (mask sui log).
"""
import http.cookiejar
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import Cookie
from pathlib import Path

WIN = "--win" in sys.argv
INLINE = "--inline" in sys.argv
CTX = None
MSG_FILE = None
PULL = None
if "--pull" in sys.argv:
    _p = sys.argv.index("--pull")
    PULL = (sys.argv[_p + 1], sys.argv[_p + 2])
    MINUTES = 0
    args = []
elif "--ctx" in sys.argv:
    _i = sys.argv.index("--ctx")
    CTX = sys.argv[_i + 1]
    MINUTES = 3.0
    for _j in range(_i + 2, len(sys.argv)):
        _a = sys.argv[_j]
        if _a == "--msg":
            MSG_FILE = sys.argv[_j + 1]
        elif not _a.startswith("--"):
            try:
                MINUTES = float(_a)
            except ValueError:
                pass
    args = []
else:
    args = [a for a in sys.argv[1:] if a not in ("--win", "--inline")]
    MINUTES = float(args[1]) if len(args) > 1 else 4.0
BRIEF = args[0] if args else "/a0/usr/workdir/p14/BRIEF-P14.md"
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
    token = None
    if not WIN:
        user, password = env_mc2("AUTH_LOGIN"), env_mc2("AUTH_PASSWORD")
        call("GET", "/login")
        if user and password:
            st, body = call("POST", "/login", {"username": user, "password": password}, form=True)
            print("login:", st, "invalid:", b"Invalid" in body)
    st, raw = (0, b"")
    for path in ("/api/csrf_token", "/csrf_token"):
        st, raw = call("GET", path)
        if st == 200:
            print("csrf via", path)
            break
    if st != 200:
        print("csrf_token:", st, raw[:120].decode(errors="replace"))
        return 1
    csrf = json.loads(raw.decode())
    token, rid = csrf["token"], csrf["runtime_id"]
    cj.set_cookie(Cookie(0, "csrf_token_" + rid, token, None, False,
                         "127.0.0.1" if not WIN else "100.76.22.119",
                         False, False, "/", True, False, None, True, None, None, {}))
    if PULL:
        remote, out = PULL
        st, raw = call("GET", "/api/download_work_dir_file?" + urllib.parse.urlencode({"path": remote}),
                       headers={"X-CSRF-Token": token})
        if st == 200 and raw[:2] != b"<!":
            Path(out).write_bytes(raw)
            print("pull:", st, len(raw), "->", out)
            return 0
        print("pull fallito:", st, raw[:140].decode(errors="replace"))
        return 1
    if CTX:
        ctxid = CTX
        print("ctxid (riuso):", ctxid)
    else:
        st, raw = call("POST", "/api/chat_create", {}, headers={"X-CSRF-Token": token})
        print("chat_create:", st, raw[:120].decode(errors="replace"))
        try:
            ctx = json.loads(raw.decode())
            ctxid = ctx.get("ctxid") or ctx.get("context") or ctx.get("id")
        except Exception:
            ctxid = None
        if not ctxid:
            print("ctxid non trovato — mi fermo")
            return 1
        print("ctxid:", ctxid)
    if MSG_FILE:
        with open(MSG_FILE, encoding="utf-8") as fh:
            msg = fh.read()
        st, raw = call("POST", "/api/message_async", {"text": msg, "context": ctxid},
                       headers={"X-CSRF-Token": token})
        print("send:", st, raw[:160].decode(errors="replace"))
    elif CTX:
        print("watch-only (nessun invio)")
    else:
        if INLINE:
            with open(BRIEF, encoding="utf-8") as fh:
                msg = "Leggi ed esegui subito questo brief:\n\n" + fh.read()
        else:
            msg = "Leggi ed esegui subito %s" % BRIEF
        st, raw = call("POST", "/api/message_async", {"text": msg, "context": ctxid},
                       headers={"X-CSRF-Token": token})
        print("kickoff:", st, raw[:160].decode(errors="replace"))
    max_no = -1
    seen = 0
    end = time.time() + MINUTES * 60
    while time.time() < end:
        time.sleep(6)
        st, raw = call("POST", "/api/poll", {"context": ctxid, "log_from": 0},
                       headers={"X-CSRF-Token": token})
        try:
            data = json.loads(raw.decode())
        except Exception:
            print("poll raw:", raw[:140].decode(errors="replace"))
            continue
        for it in (data.get("logs") or []):
            if isinstance(it, dict) and it.get("no") is not None and it["no"] > max_no:
                max_no = it["no"]
                seen += 1
                c = mask(str(it.get("content") or "").replace("\n", " ")[:200])
                print("[%s] %s | %s" % (it.get("no"), it.get("type"), c))
    print("watch terminato | items visti:", seen, "| ultimo no:", max_no)
    print("CONTEXT=%s" % ctxid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
