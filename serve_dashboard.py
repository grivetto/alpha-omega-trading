#!/usr/bin/env python3
"""Serve dashboard_infra.html on port 8913 + proxy /api/infra.json -> infra aggregator (8912)"""
import os
import json
import urllib.request
from http.server import SimpleHTTPRequestHandler, HTTPServer

os.chdir("/home/sergio/denaro/denaro")
PORT = 8913
HOST = "127.0.0.1"
API_URL = "http://127.0.0.1:8912/api/infra.json"

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            self.path = "/dashboard_infra.html"
            return super().do_GET()
        if self.path.startswith("/api/infra.json"):
            try:
                with urllib.request.urlopen(API_URL, timeout=5) as r:
                    data = r.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        return super().do_GET()
    
    def log_message(self, *args):
        pass

if __name__ == "__main__":
    srv = HTTPServer((HOST, PORT), Handler)
    print(f"Dashboard server on {HOST}:{PORT} (proxy /api/infra.json -> {API_URL})")
    srv.serve_forever()
