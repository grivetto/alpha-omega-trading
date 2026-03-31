from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-color: #00ffcc;
            --accent-color: #ff0055;
            --panel-bg: rgba(0, 255, 204, 0.05);
            --border-color: #00ffcc;
            --glow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
            --glow-alert: 0 0 10px #ff0055, 0 0 20px #ff0055;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: radial-gradient(circle at 50% 50%, rgba(0, 255, 204, 0.05) 0%, transparent 60%);
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: var(--glow);
        }
        h1 { 
            text-align: center; 
            border-bottom: 2px solid var(--border-color); 
            padding-bottom: 10px; 
            margin-bottom: 30px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 20px;
            border-radius: 5px;
            box-shadow: inset 0 0 15px rgba(0, 255, 204, 0.1), 0 0 10px rgba(0, 255, 204, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -50%; left: -50%; width: 200%; height: 200%;
            background: linear-gradient(to bottom, rgba(0, 255, 204, 0.1) 0%, transparent 100%);
            transform: rotate(45deg);
            animation: radar 10s linear infinite;
            pointer-events: none;
        }
        @keyframes radar {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .status-online { color: #00ff00; text-shadow: 0 0 8px #00ff00; }
        .status-active { color: #ffff00; text-shadow: 0 0 8px #ffff00; animation: blink 1.5s infinite; }
        .status-alert { color: #ff0055; text-shadow: 0 0 8px #ff0055; animation: blink 0.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid rgba(0,255,204,0.3); padding: 10px; text-align: left; }
        th { background: rgba(0,255,204,0.15); color: #fff; text-shadow: 0 0 5px #fff; }
        tr:hover { background: rgba(0,255,204,0.1); }
        .metric-box { 
            font-size: 1.4em; 
            border: 1px solid var(--border-color); 
            padding: 15px; 
            text-align: center; 
            color: var(--text-color); 
            text-shadow: var(--glow); 
            margin-top: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 3px;
        }
        .metric-title { font-size: 0.5em; color: #888; text-shadow: none; letter-spacing: 1px; margin-bottom: 5px; }
        ul { list-style-type: none; padding-left: 0; }
        li { margin-bottom: 12px; padding: 10px; border-left: 3px solid var(--border-color); background: rgba(0,255,204,0.05); }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA // ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.2em;">
        <span>SYS.CORE: <span class="status-online">ONLINE</span></span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span>UPTIME: <span id="uptime">00:00:00</span></span> &nbsp;&nbsp;|&nbsp;&nbsp; 
        <span>DEFCON: <span class="status-alert">3</span></span>
        <br><br>
        <span style="font-weight: bold; color: #00ffcc; text-shadow: 0 0 10px #00ffcc;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>SQUADRA</th><th>RUOLO</th><th>TARGET</th><th>STATO</th></tr>
                <tr><td>🐺 SQUADRA_ALPHA</td><td>Scalper</td><td>Binance</td><td><span class="status-active">ENGAGED</span></td></tr>
                <tr><td>🦅 SQUADRA_DELTA</td><td>Order Flow</td><td>Cross-CEX</td><td><span class="status-online">STANDBY</span></td></tr>
                <tr><td>🦂 SQUADRA_GAMMA</td><td>Pairs Trading</td><td>Bitget</td><td><span class="status-active">ARBITRAGE</span></td></tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <p style="color: #aaa; font-size: 0.9em; border-bottom: 1px solid #333; padding-bottom: 10px;">PROCESSI BACKGROUND OPERATIVI. NESSUNA ANOMALIA RILEVATA.</p>
            <ul>
                <li>🕴️ <b>Lo Strozzino:</b> Funding Arb <span class="status-online" style="float:right;">[ATTIVO]</span><br><span style="font-size: 0.8em; color: #888;">Yield stimato: 14.2% APY</span></li>
                <li>🧮 <b>Il Contabile:</b> DCA Engine <span class="status-online" style="float:right;">[ATTIVO]</span><br><span style="font-size: 0.8em; color: #888;">Prossimo acquisto in: 04h 22m</span></li>
                <li>👼 <b>L'Angelo Custode:</b> MEV Arbitrum <span class="status-online" style="float:right;">[ATTIVO]</span><br><span style="font-size: 0.8em; color: #888;">Mempool scanning in corso...</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 THE ORACLE // MARKET METRICS</h2>
            <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                <div class="metric-box" style="flex: 1; margin: 5px;">
                    <div class="metric-title">BTC DOMINANCE</div>
                    <div id="btc-dom">52.41%</div>
                </div>
                <div class="metric-box" style="flex: 1; margin: 5px; border-color: var(--accent-color); color: var(--accent-color); text-shadow: var(--glow-alert);">
                    <div class="metric-title" style="color: #888;">WHALE TRACKER (24H)</div>
                    <div id="whale-flow">+ $420M INFLOW</div>
                </div>
                <div class="metric-box" style="flex: 1; margin: 5px;">
                    <div class="metric-title">BINANCE SENTIMENT</div>
                    <div id="sentiment" class="status-active">EXTREME GREED (82)</div>
                </div>
                <div class="metric-box" style="flex: 1; margin: 5px; border-color: var(--accent-color); color: var(--accent-color); text-shadow: var(--glow-alert);">
                    <div class="metric-title" style="color: #888;">LIQUIDATION HEATMAP</div>
                    <div id="liq-heat">HEAVY @ $68.5K</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let sec = 0;
        setInterval(() => {
            sec++;
            let h = Math.floor(sec / 3600).toString().padStart(2, '0');
            let m = Math.floor((sec % 3600) / 60).toString().padStart(2, '0');
            let s = (sec % 60).toString().padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
            
            if(Math.random() > 0.6) {
                let dom = (52.40 + (Math.random() * 0.1 - 0.05)).toFixed(2);
                document.getElementById('btc-dom').innerText = `${dom}%`;
            }
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
