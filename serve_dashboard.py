#!/usr/bin/env python3
"""
Denaro - Dashboard server (:8913).

Serve la dashboard HTML "Denaro Neon Grid" e fa da proxy verso l'Infra
Aggregator (:8912), aggiungendo una last-good cache per non lasciare mai la
pagina senza dati.

Perche' esiste (incident 2026-09-10):
  * la unit systemd denaro-dashboard-mc2.service puntava a
    /home/sergio/denaro/serve_dashboard.py, file che NON esisteva piu':
    al primo restart il servizio sarebbe andato in crash-loop con
    "can't open file ... [Errno 2]" e la dashboard sarebbe rimasta nera;
  * con HTTPServer mono-thread una singola richiesta lenta all'aggregator
    bloccava tutta la dashboard;
  * se l'aggregator era giu', /api/infra.json tornava un errore e la pagina
    mostrava "SIGNAL LOST" anche se il dato buono di 30 secondi prima c'era.

Cosa fa adesso:
  GET /                 -> dashboard HTML (no-store)
  GET /dashboard        -> idem
  GET /dashboard/       -> idem (prima era 404)
  GET /api/infra.json   -> JSON dell'aggregator (proxy) + fallback last-good
  GET /infra.json       -> alias di /api/infra.json
  GET /healthz          -> stato del servizio in JSON

Configurazione (env var, override da riga di comando):
  DASH_HOST         default 127.0.0.1
  DASH_PORT         default 8913
  DASH_HTML_DIR     default /home/sergio/denaro/denaro
  DASH_HTML_FILE    default dashboard_infra.html
  AGG_URL           default http://127.0.0.1:8912/infra.json
  AGG_TIMEOUT       default 6 (secondi)
  DASH_CACHE_FILE   default /home/sergio/denaro/health/infra_last_good.json
  DASH_STALE_WARN   default 120 (secondi: oltre questo il JSON e' "stale")

Uso:
  python3 serve_dashboard.py                 # produzione
  python3 serve_dashboard.py --port 8914     # istanza di test
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML_ROUTES = {"/", "/dashboard", "/dashboard/", "/index.html"}
JSON_ROUTES = {"/api/infra.json", "/infra.json", "/api/infra", "/infra"}


def log(msg: str) -> None:
    """Log su stderr -> journal systemd (flush immediato)."""
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), file=sys.stderr, flush=True)


class AggregatorClient:
    """Client con cache last-good per l'Infra Aggregator."""

    def __init__(self, urls, timeout: float, cache_file: Path, stale_warn: float) -> None:
        # Piu' URL in ordine di preferenza (failover): la dashboard su mc2 legge
        # l'aggregatore COMPLETO di MARCODG1 via tunnel ([::1]:8912) e solo se
        # questo non risponde usa quello locale.
        if isinstance(urls, str):
            urls = [u.strip() for u in urls.split(",") if u.strip()]
        self.urls = list(urls) or ["http://127.0.0.1:8912/infra.json"]
        self.url = self.urls[0]
        self._preferred = 0
        self.timeout = timeout
        self.cache_file = cache_file
        self.stale_warn = stale_warn
        self._lock = threading.Lock()
        self._last_good: bytes | None = None
        self._last_good_ts: float = 0.0
        self._last_error: str = ""
        self._load_disk_cache()

    # ---------- cache su disco ----------
    def _load_disk_cache(self) -> None:
        try:
            if self.cache_file.is_file():
                raw = self.cache_file.read_bytes()
                json.loads(raw.decode("utf-8", "replace"))  # validazione
                with self._lock:
                    self._last_good = raw
                    self._last_good_ts = self.cache_file.stat().st_mtime
                log("cache su disco caricata (%d bytes, eta' %.0fs)" % (len(raw), time.time() - self._last_good_ts))
        except Exception as exc:  # cache corrotta -> si ignora
            log("cache su disco ignorata: %s" % exc)

    def _save_disk_cache(self, raw: bytes) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_file.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, self.cache_file)  # atomico
        except Exception as exc:
            log("impossibile scrivere la cache su disco: %s" % exc)

    # ---------- fetch ----------
    def fetch(self) -> tuple[bytes, dict]:
        """Ritorna (json_bytes, meta). Non solleva mai: degrada sulla cache."""
        errors = []
        order = list(range(len(self.urls)))
        if self._preferred:
            order = [self._preferred] + [i for i in order if i != self._preferred]
        for i in order:
            url = self.urls[i]
            try:
                req = urllib.request.Request(url, headers={"Cache-Control": "no-store", "User-Agent": "denaro-dashboard/2"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                json.loads(raw.decode("utf-8", "replace"))  # il payload deve essere JSON valido
                now = time.time()
                with self._lock:
                    self._last_good = raw
                    self._last_good_ts = now
                    self._last_error = ""
                self._save_disk_cache(raw)
                if self._preferred != i:
                    log("aggregatore attivo: %s" % url)
                    self._preferred = i
                return raw, {"source": "live", "age_s": 0.0, "stale": False, "error": "", "url": url}
            except Exception as exc:
                errors.append("%s -> %s: %s" % (url, type(exc).__name__, exc))
        try:
            raise RuntimeError("; ".join(errors) or "nessun aggregatore configurato")
        except Exception as exc:
            msg = "%s: %s" % (type(exc).__name__, exc)
            with self._lock:
                self._last_error = msg
                raw = self._last_good
                ts = self._last_good_ts
            if raw is None:
                log("aggregator non raggiungibile e nessuna cache: %s" % msg)
                return b"", {"source": "none", "age_s": 0.0, "stale": True, "error": msg}
            age = max(0.0, time.time() - ts)
            log("aggregator KO (%s) -> servo cache di %.0fs fa" % (msg, age))
            return raw, {"source": "cache", "age_s": age, "stale": age > self.stale_warn, "error": msg}

    def status(self) -> dict:
        with self._lock:
            age = (time.time() - self._last_good_ts) if self._last_good_ts else None
            return {
                "aggregator_url": self.urls[self._preferred] if self.urls else self.url,
                "aggregator_urls": self.urls,
                "last_good_age_s": round(age, 1) if age is not None else None,
                "last_error": self._last_error,
                "has_cache": self._last_good is not None,
            }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "DenaroDashboard/2.0"
    protocol_version = "HTTP/1.1"

    # iniettati da make_server()
    html_dir: Path = Path(".")
    html_file: str = "dashboard_infra.html"
    agg: AggregatorClient = None  # type: ignore[assignment]

    # ---------- helper ----------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None, head_only: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head_only and body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _html_path(self) -> Path:
        return Path(self.html_dir) / self.html_file

    def _serve_html(self, head_only: bool = False) -> None:
        path = self._html_path()
        try:
            body = path.read_bytes()
        except OSError as exc:
            log("HTML non leggibile %s: %s" % (path, exc))
            self._send(500, ("dashboard HTML non trovato: %s" % path).encode(), "text/plain; charset=utf-8", head_only=head_only)
            return
        self._send(200, body, "text/html; charset=utf-8", {"X-Denaro-Html": path.name}, head_only=head_only)

    def _serve_json(self, head_only: bool = False) -> None:
        raw, meta = self.agg.fetch()
        if not raw:
            payload = json.dumps({"error": "aggregator irraggiungibile", "detail": meta["error"], "source": "none"}).encode()
            self._send(503, payload, "application/json; charset=utf-8", {"X-Denaro-Source": "none"}, head_only=head_only)
            return
        # annota la freschezza senza rompere i consumer esistenti
        try:
            obj = json.loads(raw.decode("utf-8", "replace"))
            obj["dashboard"] = {
                "source": meta["source"],
                "cache_age_s": round(meta["age_s"], 1),
                "stale": meta["stale"],
                "served_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            body = json.dumps(obj).encode("utf-8")
        except Exception:
            body = raw
        self._send(200, body, "application/json; charset=utf-8",
                   {"X-Denaro-Source": meta["source"], "X-Denaro-Stale": "1" if meta["stale"] else "0"},
                   head_only=head_only)

    def _serve_healthz(self, head_only: bool = False) -> None:
        st = self.agg.status()
        st["service"] = "denaro-dashboard"
        st["html"] = str(self._html_path())
        st["html_exists"] = self._html_path().is_file()
        st["ok"] = bool(st["has_cache"]) and st["html_exists"]
        body = json.dumps(st).encode()
        self._send(200 if st["ok"] else 503, body, "application/json; charset=utf-8", head_only=head_only)

    # ---------- HTTP ----------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in HTML_ROUTES or path == "":
            self._serve_html()
        elif path in {r.rstrip("/") or "/" for r in JSON_ROUTES}:
            self._serve_json()
        elif path == "/healthz":
            self._serve_healthz()
        else:
            self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")

    def do_HEAD(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in HTML_ROUTES:
            self._serve_html(head_only=True)
        elif path in {r.rstrip("/") or "/" for r in JSON_ROUTES}:
            self._serve_json(head_only=True)
        elif path == "/healthz":
            self._serve_healthz(head_only=True)
        else:
            self._send(404, b"", "application/json; charset=utf-8", head_only=True)

    def log_message(self, fmt: str, *args) -> None:  # silenzia il log per-request
        pass


def make_server(host: str, port: int, html_dir: Path, html_file: str, agg: AggregatorClient) -> ThreadingHTTPServer:
    DashboardHandler.html_dir = html_dir
    DashboardHandler.html_file = html_file
    DashboardHandler.agg = agg
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.allow_reuse_address = True
    return ThreadingHTTPServer((host, port), DashboardHandler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Denaro dashboard server (:8913)")
    ap.add_argument("--host", default=os.getenv("DASH_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("DASH_PORT", "8913")))
    ap.add_argument("--html-dir", default=os.getenv("DASH_HTML_DIR", "/home/sergio/denaro/denaro"))
    ap.add_argument("--html-file", default=os.getenv("DASH_HTML_FILE", "dashboard_infra.html"))
    ap.add_argument("--agg-urls", default=os.getenv("AGG_URLS") or os.getenv("AGG_URL", "http://127.0.0.1:8912/infra.json"),
                    help="URL dell'aggregatore separati da virgola, in ordine di preferenza (failover)")
    ap.add_argument("--agg-timeout", type=float, default=float(os.getenv("AGG_TIMEOUT", "6")))
    ap.add_argument("--cache-file", default=os.getenv("DASH_CACHE_FILE", "/home/sergio/denaro/health/infra_last_good.json"))
    ap.add_argument("--stale-warn", type=float, default=float(os.getenv("DASH_STALE_WARN", "120")))
    args = ap.parse_args(argv)

    html_dir = Path(args.html_dir)
    agg = AggregatorClient(args.agg_urls, args.agg_timeout, Path(args.cache_file), args.stale_warn)

    try:
        srv = make_server(args.host, args.port, html_dir, args.html_file, agg)
    except OSError as exc:
        log("bind %s:%d fallito: %s" % (args.host, args.port, exc))
        if getattr(exc, "errno", None) == 98:
            log("porta occupata: 'ss -ltnp | grep :%d' e termina il processo estraneo" % args.port)
        return 2

    html_path = html_dir / args.html_file
    log("dashboard su http://%s:%d  html=%s (%s)  aggregator=%s" % (
        args.host, args.port, html_path, "ok" if html_path.is_file() else "MANCANTE!", " , ".join(agg.urls)))
    if not html_path.is_file():
        log("ATTENZIONE: il file HTML non esiste, la pagina rispondera' 500")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("stop richiesto")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
