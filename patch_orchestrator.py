#!/usr/bin/env python3
"""Patch orchestrator.py to serve static files and load dashboard/index.html"""
import re

PATH = "/home/sergio/denaro/orchestrator.py"

with open(PATH) as f:
    content = f.read()

# Patch 1: Replace get_dashboard_html to read from file
old_func_start = content.find("def get_dashboard_html(self):")
old_return = content.find("return '''", old_func_start)
old_end = content.find("'''\n", old_return + 10)
if old_end == -1:
    old_end = content.find("'''", old_return + 10)
old_func = content[old_func_start:old_end + 3]

new_func = """def get_dashboard_html(self):
        try:
            html_file = BASE_DIR / "dashboard" / "index.html"
            with open(str(html_file), "r") as f:
                return f.read()
        except Exception as e:
            return f"<!DOCTYPE html><html><body><h1>Dashboard Error</h1><p>{e}</p></body></html>"""

content = content.replace(old_func, new_func)
print(f" - Patched get_dashboard_html() [{len(old_func)} chars -> {len(new_func)} chars]")

# Patch 2: Add static file serving before else:404
# Find the "else:" right before log_message
old_else = """        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):"""

new_else = """        elif self.path.startswith('/public/'):
            self.serve_static()
        elif self.path == '/squadra.log':
            self.serve_file(BASE_DIR / 'squadra' / 'squadra.log', 'text/plain')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):"""

content = content.replace(old_else, new_else)
print(f" - Patched do_GET() to add static file routes")

# Patch 3: Add serve_static and serve_file methods before log_message
old_log_block = """    def log_message(self, format, *args):
        pass  # Suppress HTTP log spam
    
    def get_dashboard_html(self):"""

new_methods = """    def serve_static(self):
        \"\"\"Serve files from dashboard/ and dashboard/public/ directories\"\"\"
        path = self.path.lstrip('/')
        file_path = BASE_DIR / 'dashboard' / path
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        ext = file_path.suffix.lower()
        mime = {
            '.json': 'application/json',
            '.html': 'text/html',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
        }.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        with open(str(file_path), 'rb') as f:
            self.wfile.write(f.read())
    
    def serve_file(self, path, mime):
        \"\"\"Serve an arbitrary file with given MIME type\"\"\"
        path_str = str(path)
        try:
            with open(path_str, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP log spam
    
    def get_dashboard_html(self):"""

content = content.replace(old_log_block, new_methods)
print(f" - Added serve_static() and serve_file() methods")

with open(PATH, "w") as f:
    f.write(content)

print("Done! orchestrator.py patched successfully.")
