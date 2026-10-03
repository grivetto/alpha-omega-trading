#!/usr/bin/env python3
"""Legge la config modello del contesto A0 via plugin _model_config (masked)."""
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
CTX = sys.argv[sys.argv.index("--ctx") + 1] if "--ctx" in sys.argv else ""
BASE = "http://100.76.22.119:50080" if WIN else "http://127.0.0.1:50080"


def env_mc2(key):
    out = subprocess.run(["docker", "exec", "agent-zero", "sh", "-c", "cat /a0/.env"],
                         capture_output=True, text=True, timeout=30).stdout
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def mask(s):
    return re.sub(r"(sk-|or-|AIza|nvapi-|gsk_|Bearer )[A-Za-z0-9_\-]{6,}", "[REDACTED]", str(s or ""))


def mask_obj(o, depth=0):
    if depth > 6:
        return "..."
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower():
                out[k] = "[MASKED]" if v else v
            else:
                out[k] = mask_obj(v, depth + 1)
        return out
    if isinstance(o, list):
        return [mask_obj(v, depth + 1) for v in o[:12]]
    if isinstance(o, str):
        return mask(o)
    return o


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

    if "--presets" in sys.argv:
        st, raw = call("POST", "/api/plugins/_model_config/model_presets",
                       {"action": "get"}, headers={"X-CSRF-Token": token})
        try:
            d = json.loads(raw.decode(errors="replace"))
            print(mask(json.dumps(mask_obj(d), ensure_ascii=False))[:2200])
        except Exception:
            print(mask(raw[:600].decode(errors="replace")))
        return
    if "--set-preset" in sys.argv:
        name = sys.argv[sys.argv.index("--set-preset") + 1]
        chat = {"provider": "openrouter", "name": "deepseek/deepseek-v4-flash", "api_base": "",
                "ctx_length": 128000, "ctx_history": 0.7, "vision": False, "max_embeds": 10,
                "rl_requests": 0, "rl_input": 0, "rl_output": 0}
        cfg = {"chat_model": dict(chat), "utility_model": dict(chat)}
        st, raw = call("POST", "/api/plugins/_model_config/model_config_set",
                       {"preset_name": name, "config": cfg},
                       headers={"X-CSRF-Token": token})
        print("SET-PRESET", name, "->", st, raw[:200].decode(errors="replace"))
        return
    if "--set-or" in sys.argv:
        ov = {"provider": "openrouter", "name": "deepseek/deepseek-v4-flash", "api_base": "",
              "ctx_length": 128000, "ctx_history": 0.7, "vision": False, "max_embeds": 10,
              "rl_requests": 0, "rl_input": 0, "rl_output": 0}
        st, raw = call("POST", "/api/plugins/_model_config/model_override",
                       {"action": "set", "context_id": CTX, "override": ov},
                       headers={"X-CSRF-Token": token})
        print("SET:", st, raw[:200].decode(errors="replace"))
        return
    if "--clear" in sys.argv:
        st, raw = call("POST", "/api/plugins/_model_config/model_override",
                       {"action": "clear", "context_id": CTX},
                       headers={"X-CSRF-Token": token})
        print("CLEAR:", st, raw[:200].decode(errors="replace"))
        return

    st, raw = call("POST", "/api/plugins/_model_config/model_config_get",
                   {"context_id": CTX}, headers={"X-CSRF-Token": token})
    print("GET", st)
    try:
        d = json.loads(raw.decode(errors="replace"))
    except Exception:
        print(raw[:300]); return
    print("configured_preset:", d.get("configured_preset"), "| selected:", d.get("selected_preset"))
    print("model_configured_label:", d.get("model_configured_label"))
    print("chat_model:", mask_obj((d.get("config") or {}).get("chat_model")))
    print("api_key_status:", {k: v for k, v in (d.get("api_key_status") or {}).items() if k in ("google", "gemini", "deepseek", "openrouter", "groq", "nvidia_nim", "xai", "mistral", "zai", "moonshot")})
    presets = d.get("presets") or []
    print("presets:")
    for p in presets[:10]:
        cm = (p.get("config") or {}).get("chat_model") or {}
        print("   -", p.get("name"), "|", cm.get("provider"), "/", cm.get("name"), "| key:", "[MASKED]" if cm.get("api_key") else "-")

    st, raw = call("POST", "/api/plugins/_model_config/model_override",
                   {"action": "get", "context_id": CTX}, headers={"X-CSRF-Token": token})
    print("OVERRIDE get:", st, mask_obj(json.loads(raw.decode(errors="replace"))) if st == 200 else raw[:200])


if __name__ == "__main__":
    main()
