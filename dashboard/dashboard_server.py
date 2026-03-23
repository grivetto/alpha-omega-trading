#!/usr/bin/env python3
"""
Dashboard Server - Multi-Coin + Grid Trading
"""

import http.server
import socketserver
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
BASE_DIR = '/root/.openclaw/workspace'
DASHBOARD_DIR = os.path.join(BASE_DIR, 'dashboard')

STATUS_FILE = os.path.join(BASE_DIR, 'multi_status.json')
GRID_STATUS_FILE = os.path.join(BASE_DIR, 'grid_status.json')
QUANT_STATUS_FILE = os.path.join(BASE_DIR, 'quant_status.json')
CRYPTOCOM_STATUS_FILE = os.path.join(BASE_DIR, 'cryptocom_status.json')

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
        elif self.path == '/grid' or self.path == '/grid.html':
            self.path = '/grid.html'
        elif self.path == '/multi_status.json' or self.path.startswith('/multi_status.json?'):
            self.send_json_file(STATUS_FILE)
            return
        elif self.path == '/grid_status.json' or self.path.startswith('/grid_status.json?'):
            self.send_json_file(GRID_STATUS_FILE)
            return
        elif self.path == '/quant_status.json' or self.path.startswith('/quant_status.json?'):
            self.send_json_file(QUANT_STATUS_FILE)
            return
        elif self.path == '/cryptocom_status.json' or self.path.startswith('/cryptocom_status.json?'):
            self.send_json_file(CRYPTOCOM_STATUS_FILE)
            return
        elif self.path == '/fleet_stats.json' or self.path.startswith('/fleet_stats.json?'):
            self.send_json_file(os.path.join(DASHBOARD_DIR, 'fleet_stats.json'))
            return
        elif self.path == '/trades_6h.json' or self.path.startswith('/trades_6h.json?'):
            self.send_json_file(os.path.join(DASHBOARD_DIR, 'trades_6h.json'))
            return
        elif self.path == '/trades' or self.path == '/trades.html':
            self.path = '/trades.html'
        return super().do_GET()
    
    def send_json_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data.encode())
        except Exception as e:
            self.send_error(404, str(e))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    print(f"🚀 Dashboard: http://localhost:{PORT}")
    with ThreadedHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.serve_forever()
