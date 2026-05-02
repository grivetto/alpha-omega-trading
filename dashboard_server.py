import os
import json
import socketserver
import http.server
from datetime import datetime

PORT = 8080

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            # Load fleet status
            fleet_data = {}
            try:
                status_file = "/home/sergio/denaro/.tmp/fleet_status.json"
                if os.path.exists(status_file):
                    with open(status_file) as f:
                        fleet_data = json.load(f)
            except:
                pass

            # Extract values with safe defaults
            vault = fleet_data.get('portfolio_eur', 0.0)
            reference_capital = fleet_data.get('reference_capital_eur', 300.0)
            today_profit_eur = fleet_data.get('today_profit_eur', 0.0)
            today_trades = fleet_data.get('today_trades', 0)
            total_invested = fleet_data.get('totals', {}).get('invested_eur', 0.0)
            total_profit = fleet_data.get('totals', {}).get('profit_eur', 0.0)
            total_drawdown = fleet_data.get('total_drawdown_pct', 0.0)
            absolute_drawdown = fleet_data.get('absolute_drawdown_pct', 0.0)
            atr = fleet_data.get('atr_eur', 0)
            atr_pct = fleet_data.get('atr_pct')
            kill_switch_triggered = fleet_data.get('kill_switch_triggered', False)
            portfolio_details = fleet_data.get('portfolio_details', {})
            nodes = fleet_data.get('nodes', {})

            # Fleet stats table data
            fleet_stats = {}
            for node_name, node_data in nodes.items():
                status_val = node_data.get('status', 'UNKNOWN')
                ram_pct = round((1 - node_data.get('memory_available_mb', 0) / 4096) * 100, 1) if node_data.get('memory_available_mb', 0) > 0 else 0
                grid_bot = node_data.get('grid_bot', {})
                last_log_age = grid_bot.get('last_log_age_s', 999999)
                grid_pid = grid_bot.get('pid', 'N/A')
                invested = grid_bot.get('invested_eur', 0)
                profit = grid_bot.get('profit_eur', 0)
                balance = node_data.get('binance_balance_eur', 0)
                fleet_stats[f'denaro_{node_name}'] = {
                    'status': status_val,
                    'mem': ram_pct,
                    'log_age_s': last_log_age,
                    'grid_pid': grid_pid,
                    'invested': invested,
                    'profit': profit,
                    'balance': balance,
                }

            total_bots = len(fleet_stats)
            alive_bots = sum(1 for s in fleet_stats.values() if isinstance(s, dict) and s.get('status') in ['ALIVE', 'ONLINE'])

            # System specs
            sys_os = 'Linux'
            cpu_usage = '4.2'
            ram_usage = '76.4'
            swap_usage = '12.0'
            try:
                import platform, psutil
                sys_os = platform.system() + ' ' + platform.release()
                cpu_usage = str(psutil.cpu_percent(interval=0.1))
                ram_info = psutil.virtual_memory()
                ram_usage = str(round(ram_info.percent, 1))
                swap_usage = str(round(psutil.swap_memory().percent, 1))
            except:
                pass

            # Build HTML
            profit_color = '#00e676' if today_profit_eur >= 0 else '#ef4444'
            dd_color = '#ef4444' if total_drawdown > 5.0 else ('#fbbf24' if total_drawdown > 2.0 else 'var(--primary)')
            abs_dd_color = '#ef4444' if absolute_drawdown > 10 else ('#fbbf24' if absolute_drawdown > 5 else 'var(--primary)')
            ks_color = '#ef4444' if kill_switch_triggered else 'var(--primary)'
            atr_str = f'{atr:.4f}&euro; ({atr_pct:.3f}%)' if atr_pct else f'{atr}&euro; (N/A)'
            grid_profit_color = '#00e676' if total_profit >= 0 else '#ef4444'

            html = (
                '<!DOCTYPE html>\n'
                '<html>\n'
                '<head>\n'
                '<meta charset="UTF-8">\n'
                '<title>Orbital Command | Neon Squad</title>\n'
                '<meta http-equiv="refresh" content="10">\n'
                '<style>\n'
                ':root { --bg: #0b0f19; --panel: #131a2a; --primary: #00e676; --secondary: #00b4d8; --accent: #ff007a; --text: #e2e8f0; --border: #1e293b; }\n'
                'body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; margin: 0; padding: 30px; }\n'
                'h1 { color: var(--primary); border-bottom: 2px solid var(--border); padding-bottom: 15px; margin-bottom: 30px; display: flex; align-items: center; gap: 10px; }\n'
                '.vault { background: linear-gradient(135deg, rgba(0,180,216,0.1), rgba(0,230,118,0.1)); border: 1px solid var(--secondary); border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: center; font-size: 1.5rem; }\n'
                '.vault-val { color: var(--primary); font-size: 2.2rem; font-weight: bold; display: block; margin-top: 5px; text-shadow: 0 0 15px rgba(0,230,118,0.3); }\n'
                '.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 25px; margin-bottom: 25px; }\n'
                '.row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }\n'
                '.ok { color: var(--primary); font-weight: 600; } .dead { color: #ef4444; font-weight: 600; } .dim { color: #64748b; }\n'
                'table { width: 100%; border-collapse: collapse; margin-top: 15px; }\n'
                'th { background: rgba(255,255,255,0.02); color: var(--secondary); padding: 12px; text-align: left; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }\n'
                'td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.03); }\n'
                'tr:hover td { background: rgba(255,255,255,0.02); }\n'
                '.footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); color: #64748b; font-size: 0.9rem; }\n'
                '.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }\n'
                '.kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; font-size: 1.1rem; }\n'
                '.kpi strong { color: var(--primary); font-weight: bold; font-size: 1.3rem; }\n'
                '</style>\n'
                '</head>\n'
                '<body>\n'
                '<h1>&#128640; ORBITAL COMMAND <span style="color:#64748b;font-size:1rem;margin-left:auto;">NEON SQUAD v2.0</span></h1>\n'
                '\n<div class="vault">\n'
                '&#128737;&#65039; CASSAFORTE PORTFOLIO\n'
                '<span class="vault-val">&euro;' + f'{vault:.2f}' + '</span>\n'
                '<span style="font-size:0.9rem;color:#64748b;"> (ref: &euro;' + f'{reference_capital:.2f}' + ')</span>\n'
                '</div>\n'
                '\n<div class="kpi-grid">\n'
                '<div class="kpi" style="border-color:#00e676;background:linear-gradient(135deg,rgba(0,230,118,0.1),rgba(168,85,247,0.1))">\n'
                '<span style="color:#64748b;">&#9889; OGGI</span><br>\n'
                '<strong style="color:' + profit_color + ';">&euro;' + f'{today_profit_eur:.2f}' + '</strong>\n'
                '<span style="color:#64748b;font-size:0.9rem;"> | ' + f'{today_trades}' + ' cicli grid</span>\n'
                '</div>\n'
                '<div class="kpi" style="border-color:#a855f7;background:linear-gradient(135deg,rgba(168,85,247,0.1),rgba(0,230,118,0.1))">\n'
                '<span style="color:#64748b;">&#9881; TRADING</span><br>\n'
                '<strong style="color:var(--primary);">&euro;' + f'{total_invested:.2f}' + '</strong>\n'
                '<span style="color:#64748b;font-size:0.9rem;"> investito | P&L: <span style="color:' + grid_profit_color + ';">&euro;' + f'{total_profit:.2f}' + '</span></span>\n'
                '</div>\n'
                '<div class="kpi" style="border-color:#ff007a;background:linear-gradient(135deg,rgba(255,0,122,0.1),rgba(255,200,0,0.1))">\n'
                '<span style="color:#64748b;">&#128073; DRAWDOWN</span><br>\n'
                '<strong style="color:' + dd_color + ';">' + f'{total_drawdown:.2f}%</strong>\n'
                '<span style="color:#64748b;font-size:0.9rem;"> (vs start: <span style="color:' + abs_dd_color + ';">' + f'{absolute_drawdown:.2f}%</span>)</span>\n'
                '</div>\n'
                '<div class="kpi" style="border-color:#00b4d8;background:linear-gradient(135deg,rgba(0,180,216,0.1),rgba(0,180,216,0.05))">\n'
                '<span style="color:#64748b;">ATR SOL/EUR</span><br>\n'
                '<strong style="color:var(--primary);">' + atr_str + '</strong>\n'
                '<span style="color:#64748b;font-size:0.9rem;"> volatilit&agrave; 24h</span>\n'
                '</div>\n'
                '</div>\n'
                '\n<div class="panel">\n'
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">\n'
                '<h2 style="margin:0;color:var(--secondary);">&#9888; KILL SWITCH</h2>\n'
                '<span style="color:' + ks_color + ';font-weight:bold;font-size:1.1rem;">' + ('&#9888; TRIGGERED' if kill_switch_triggered else '&#128737; ARMED @ 3%') + '</span>\n'
                '</div>\n'
                '<div class="row"><span>Threshold</span><span class="dim">3% drawdown vs portfolio</span></div>\n'
                '<div class="row"><span>Azione</span><span class="dim">Chiude tutti gli ordini aperti</span></div>\n'
                '<div class="row"><span>Stato</span><span class="' + ('dead' if kill_switch_triggered else 'ok') + '">' + ('ATTIVATO' if kill_switch_triggered else 'IN SERVIZIO') + '</span></div>\n'
                '</div>\n'
                '\n<div class="panel">\n'
                '<h2 style="margin:0 0 15px 0;color:var(--secondary);">&#128187; SYSTEM TELEMETRY</h2>\n'
                '<div class="row"><span>OS</span><span class="dim">' + sys_os + '</span></div>\n'
                '<div class="row"><span>CPU</span><span class="dim">' + cpu_usage + '%</span></div>\n'
                '<div class="row"><span>RAM</span><span class="dim">' + ram_usage + '%</span></div>\n'
                '<div class="row"><span>Bots attivi</span><span class="ok">' + f'{alive_bots}/{total_bots}' + '</span></div>\n'
                '</div>\n'
                '\n<div class="panel">\n'
                '<h2 style="margin:0 0 15px 0;color:var(--secondary);">&#128640; DENARO FLEET</h2>\n'
                '<table>\n'
                '<tr><th>Node</th><th>Status</th><th>Grid PID</th><th>Balance</th><th>Invested</th><th>Profit</th><th>RAM</th></tr>\n'
            )

            for bot_name, stats in fleet_stats.items():
                if isinstance(stats, dict):
                    sc = 'ok' if stats.get('status') in ['ALIVE', 'ONLINE', 'CONTROLLER'] else 'dead'
                    pc = '#00e676' if stats.get('profit', 0) >= 0 else '#ef4444'
                    lag = stats.get('log_age_s', 999999)
                    last_ping = f'{lag:.0f}s ago' if lag < 9999 else 'N/A'
                    html += (
                        '<tr>'
                        '<td style="font-weight:500;">' + bot_name + '</td>'
                        '<td class="' + sc + '">&#9679; ' + stats.get('status', 'UNKNOWN') + '</td>'
                        '<td class="dim">' + str(stats.get('grid_pid', 'N/A')) + '</td>'
                        '<td class="dim">&euro;' + f'{stats.get("balance", 0):.2f}' + '</td>'
                        '<td class="dim">&euro;' + f'{stats.get("invested", 0):.2f}' + '</td>'
                        '<td style="color:' + pc + ';">&euro;' + f'{stats.get("profit", 0):.2f}' + '</td>'
                        '<td class="dim">' + f'{stats.get("mem", 0):.1f}%</td>'
                        '</tr>\n'
                    )

            html += (
                '</table>\n'
                '</div>\n'
                '\n<div class="panel">\n'
                '<h2 style="margin:0 0 15px 0;color:var(--secondary);">&#128181; PORTFOLIO ASSETS</h2>\n'
                '<table>\n'
                '<tr><th>Asset</th><th>Qty</th><th>Price EUR</th><th>Value EUR</th></tr>\n'
            )

            for cur, info in sorted(portfolio_details.items(), key=lambda x: -x[1].get('eur', 0)):
                eur_val = info.get('eur', 0)
                if eur_val >= 0.10:
                    html += (
                        '<tr>'
                        '<td style="font-weight:500;">' + cur + '</td>'
                        '<td class="dim">' + f'{info.get("qty", 0):.6f}' + '</td>'
                        '<td class="dim">&euro;' + f'{info.get("price", 0):.4f}' + '</td>'
                        '<td style="color:var(--primary);">&euro;' + f'{eur_val:.2f}' + '</td>'
                        '</tr>\n'
                    )

            html += (
                '</table>\n'
                '</div>\n'
                '\n<div class="footer">&#128257; Aggiornamento automatico ogni 10s &bull; Denaro Autonomous Trading Infrastructure</div>\n'
                '</body>\n'
                '</html>\n'
            )

            self.wfile.write(html.encode('utf-8'))

        elif self.path == '/api/v1/fleet/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status_file = "/home/sergio/denaro/.tmp/fleet_status.json"
            if os.path.exists(status_file):
                with open(status_file) as f:
                    data = json.load(f)
                self.wfile.write(json.dumps(data).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"error": "no data yet"}).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()
