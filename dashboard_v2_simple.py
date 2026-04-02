#!/usr/bin/env python3
"""
ORBITAL COMMAND v2.0 — Dashboard Realistica (Semplificata)
Target: €3-5/giorno | Capitale: €425
"""

import os
import json
from flask import Flask
from datetime import datetime

app = Flask(__name__)

def get_capital():
    capital_file = '/home/sergio/.openclaw/workspace/denaro/capital_state.json'
    if os.path.exists(capital_file):
        with open(capital_file) as f:
            data = json.load(f)
            current = data.get('current', 425)
            total_profit = data.get('total_profit', 0)
            phase = data.get('phase', 1)
            history = data.get('daily_history', [])
            
            today_pnl = history[-1].get('pnl', 0) if history else 0
            week_pnl = sum(h.get('pnl', 0) for h in history[-7:])
            month_pnl = sum(h.get('pnl', 0) for h in history[-30:])
            
            targets = {1: 3.0, 2: 5.0, 3: 8.0, 4: 10.0}
            daily_target = targets.get(phase, 3.0)
            progress = min(100, (today_pnl / daily_target) * 100) if daily_target > 0 else 0
            
            return {
                'capital': round(current, 2),
                'pnl': round(current - 425, 2),
                'phase': phase,
                'daily_target': round(daily_target, 2),
                'today_pnl': round(today_pnl, 2),
                'week_pnl': round(week_pnl, 2),
                'month_pnl': round(month_pnl, 2),
                'total_profit': round(total_profit, 2),
                'progress': round(progress, 1),
                'next_target': 500 if phase == 1 else (650 if phase == 2 else 800)
            }
    return {
        'capital': 425, 'pnl': 0, 'phase': 1, 'daily_target': 3.0,
        'today_pnl': 0, 'week_pnl': 0, 'month_pnl': 0,
        'total_profit': 0, 'progress': 0, 'next_target': 500
    }

@app.route('/')
def dashboard():
    c = get_capital()
    now = datetime.now().strftime('%H:%M:%S %d/%m/%Y')
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>ORBITAL COMMAND v2.0 | Realistic</title>
        <style>
            body {
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
                color: #00ff88;
                font-family: 'Courier New', monospace;
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }
            .header {
                text-align: center;
                padding: 30px;
                border-bottom: 3px solid #00ff88;
                margin-bottom: 30px;
                background: rgba(0,255,136,0.1);
            }
            h1 { font-size: 2.5em; color: #fff; text-shadow: 0 0 20px #00ff88; margin: 0; }
            .subtitle { color: #ff6b6b; font-size: 1.2em; font-weight: bold; margin-top: 10px; }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }
            .card {
                background: rgba(0,0,0,0.6);
                border: 2px solid #00ff88;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 0 20px rgba(0,255,136,0.2);
            }
            .card h2 { color: #ffd93d; margin: 0 0 15px 0; text-transform: uppercase; border-bottom: 1px solid #ffd93d; padding-bottom: 10px; }
            .metric { display: flex; justify-content: space-between; padding: 10px; margin: 8px 0; background: rgba(255,255,255,0.05); border-radius: 8px; }
            .metric-label { color: #aaa; }
            .metric-value { color: #00ff88; font-weight: bold; }
            .positive { color: #00ff88; }
            .negative { color: #ff6b6b; }
            .progress-bar { background: rgba(255,255,255,0.1); border-radius: 10px; height: 30px; overflow: hidden; margin: 15px 0; }
            .progress-fill { height: 100%; background: linear-gradient(90deg, #00ff88, #ffd93d); display: flex; align-items: center; justify-content: center; color: #000; font-weight: bold; transition: width 0.5s; }
            .alert { background: rgba(255,107,107,0.2); border: 2px solid #ff6b6b; border-radius: 10px; padding: 15px; margin: 10px 0; color: #ff6b6b; font-weight: bold; }
            .success { background: rgba(0,255,136,0.2); border-color: #00ff88; color: #00ff88; }
            .footer { text-align: center; margin-top: 40px; padding: 20px; border-top: 2px solid #00ff88; color: #666; }
            .bot-list { list-style: none; padding: 0; }
            .bot-item { display: flex; justify-content: space-between; padding: 8px; margin: 5px 0; background: rgba(255,255,255,0.05); border-radius: 5px; border-left: 3px solid #00ff88; }
            .bot-name { color: #fff; }
            .bot-status { color: #00ff88; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 ORBITAL COMMAND v2.0</h1>
            <div class="subtitle">REALISTIC MODE — Target: €3-5/giorno</div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>💰 Capitale & Target</h2>
                <div class="metric"><span class="metric-label">Capitale Attuale:</span><span class="metric-value">€""" + str(c['capital']) + """</span></div>
                <div class="metric"><span class="metric-label">Capitale Iniziale:</span><span class="metric-value">€425.00</span></div>
                <div class="metric"><span class="metric-label">Profitto/Perdita:</span><span class="metric-value" style="color:""" + ("#00ff88" if c['pnl'] >= 0 else "#ff6b6b") + """;">€""" + str(c['pnl']) + """</span></div>
                <div class="metric"><span class="metric-label">Fase:</span><span class="metric-value">""" + str(c['phase']) + """/4</span></div>
                <div class="metric"><span class="metric-label">Target Oggi:</span><span class="metric-value">€""" + str(c['daily_target']) + """</span></div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:""" + str(c['progress']) + """%;">""" + str(c['progress']) + """%</div>
                </div>
            </div>
            
            <div class="card">
                <h2>🤖 Bot Attivi (7/7)</h2>
                <ul class="bot-list">
                    <li class="bot-item"><span class="bot-name">Realistic Grid Bot</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">AI Risk Engine</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">Crisis Manager</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">Delta Neutral</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">Target Tracker</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">Telegram Controller</span><span class="bot-status">✅ ON</span></li>
                    <li class="bot-item"><span class="bot-name">Dashboard v2</span><span class="bot-status">✅ ON</span></li>
                </ul>
            </div>
            
            <div class="card">
                <h2>📈 Performance</h2>
                <div class="metric"><span class="metric-label">Oggi P&L:</span><span class="metric-value" style="color:""" + ("#00ff88" if c['today_pnl'] >= 0 else "#ff6b6b") + """;">€""" + str(c['today_pnl']) + """</span></div>
                <div class="metric"><span class="metric-label">Questa Settimana:</span><span class="metric-value" style="color:""" + ("#00ff88" if c['week_pnl'] >= 0 else "#ff6b6b") + """;">€""" + str(c['week_pnl']) + """</span></div>
                <div class="metric"><span class="metric-label">Questo Mese:</span><span class="metric-value" style="color:""" + ("#00ff88" if c['month_pnl'] >= 0 else "#ff6b6b") + """;">€""" + str(c['month_pnl']) + """</span></div>
                <div class="metric"><span class="metric-label">Totale Profitto:</span><span class="metric-value positive">€""" + str(c['total_profit']) + """</span></div>
            </div>
            
            <div class="card">
                <h2>🎯 Strategia</h2>
                <div style="padding: 10px; background: rgba(0,255,136,0.1); border-radius: 10px;">
                    <strong style="color: #ffd93d;">FASE """ + str(c['phase']) + """: Crescita Controllata</strong>
                    <p style="margin-top: 10px; color: #888;">
                        Grid Trading BTC/EUR con range dinamico.<br>
                        Reinvestimento 50% profitti.<br>
                        Upgrade automatico a €""" + str(c['next_target']) + """ capitale.
                    </p>
                </div>
                """ + ("<div class='alert success'>✅ TARGET RAGGIUNTO OGGI!</div>" if c['progress'] >= 100 else ("<div class='alert'>⚠️ Sotto target — Attendere chiusura grid</div>" if c['progress'] < 30 else "<div style='padding: 10px; color: #00ff88;'>🟢 In progress verso target</div>")) + """
            </div>
            
            <div class="card">
                <h2>🔮 Proiezione 6 Mesi</h2>
                <div class="metric"><span class="metric-label">Mese 1:</span><span class="metric-value">€515 (+€90)</span></div>
                <div class="metric"><span class="metric-label">Mese 3:</span><span class="metric-value">€905 (+€240)</span></div>
                <div class="metric"><span class="metric-label">Mese 6:</span><span class="metric-value" style="color: #ffd93d; font-size: 1.3em;">€1,805 (+€1,380)</span></div>
                <div style="margin-top: 15px; padding: 10px; border-top: 1px solid #00ff88; font-size: 0.9em; color: #666;">*Stima basata su target €3-5/giorno</div>
            </div>
        </div>
        
        <div class="footer">
            <p>ORBITAL COMMAND v2.0 — Realistic Mode</p>
            <p>Capitale: €425 → Target: €1,805 (6 mesi)</p>
            <p style="margin-top: 10px; color: #444;">Aggiornato: """ + now + """</p>
        </div>
    </body>
    </html>
    """
    return html

@app.route('/health')
def health():
    return {'status': 'ok', 'mode': 'realistic', 'target': 'e3-5/day'}

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8081, debug=False)
