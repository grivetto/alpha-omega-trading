import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        body {
            background-color: #020202;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        
        h1, h2, h3 {
            text-transform: uppercase;
            margin: 0 0 10px 0;
            letter-spacing: 2px;
        }
        
        .glow-text { color: #0f0; text-shadow: 0 0 5px #0f0, 0 0 10px #0f0; }
        .glow-text-red { color: #f00; text-shadow: 0 0 5px #f00, 0 0 10px #f00; }
        .glow-text-cyan { color: #0ff; text-shadow: 0 0 5px #0ff, 0 0 10px #0ff; }
        .glow-text-purple { color: #b0f; text-shadow: 0 0 5px #b0f, 0 0 10px #b0f; }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
            position: relative;
            z-index: 2;
        }
        
        .header {
            grid-column: 1 / -1;
            border: 2px solid #0f0;
            padding: 20px;
            text-align: center;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.2) inset;
            background: rgba(0, 15, 0, 0.85);
            position: relative;
        }
        
        .panel {
            border: 1px solid #0f0;
            padding: 20px;
            background: rgba(0, 15, 0, 0.65);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1) inset;
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 0, 0.8), transparent);
            animation: scan 4s linear infinite;
            opacity: 0.5;
        }
        
        @keyframes scan {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(800px); }
        }
        
        .status-ok { color: #0f0; font-weight: bold; }
        .status-warn { color: #ff0; font-weight: bold; }
        .status-eng { color: #0ff; font-weight: bold; animation: pulse 2s infinite; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        th, td {
            border: 1px solid rgba(0, 255, 0, 0.2);
            padding: 10px;
            text-align: left;
        }
        
        th { background: rgba(0, 255, 0, 0.1); color: #0f0; }
        
        .scanline {
            width: 100vw;
            height: 100vh;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(
                to bottom,
                rgba(255, 255, 255, 0),
                rgba(255, 255, 255, 0) 50%,
                rgba(0, 0, 0, 0.15) 50%,
                rgba(0, 0, 0, 0.15)
            );
            background-size: 100% 4px;
            top: 0; left: 0;
        }
        
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid #333;
            padding: 15px;
            flex: 1;
            margin: 0 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.5) inset;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="container">
        <div class="header">
            <h1 class="glow-text">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
            <p>UPLINK ESTABLISHED | <span class="blink glow-text-cyan">SECURE CONNECTION</span> | CORE SYSTEM: ONLINE</p>
            <div style="margin-top: 15px; padding: 10px; border: 1px solid #0f0; background: rgba(0, 255, 0, 0.1); display: inline-block;">
                <span class="glow-text" style="font-weight: bold; font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
        </div>
        
        <div class="panel">
            <h2 class="glow-text-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <hr style="border-color: #f00; opacity: 0.5;">
            <table>
                <tr>
                    <th>UNIT</th>
                    <th>ROLE / DEPLOYMENT</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td><span class="glow-text-red">SQUADRA_ALPHA</span> 🐺</td>
                    <td>Scalper / Binance</td>
                    <td class="status-eng">ENGAGED [ACTIVE]</td>
                </tr>
                <tr>
                    <td><span class="glow-text-red">SQUADRA_DELTA</span> 🦅</td>
                    <td>Order Flow</td>
                    <td class="status-ok">STANDBY [READY]</td>
                </tr>
                <tr>
                    <td><span class="glow-text-red">SQUADRA_GAMMA</span> 🐍</td>
                    <td>Pairs Trading / Bitget</td>
                    <td class="status-eng">HUNTING [ACTIVE]</td>
                </tr>
            </table>
        </div>
        
        <div class="panel">
            <h2 class="glow-text-purple">👁️ PROTOCOLLO TRINITY</h2>
            <hr style="border-color: #b0f; opacity: 0.5;">
            <table>
                <tr>
                    <th>MODULE</th>
                    <th>FUNCTION</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td><span class="glow-text-purple">LO STROZZINO</span> 🦇</td>
                    <td>Funding Rate Arb</td>
                    <td class="status-ok">ONLINE (BKG)</td>
                </tr>
                <tr>
                    <td><span class="glow-text-purple">IL CONTABILE</span> 🧮</td>
                    <td>DCA Protocol</td>
                    <td class="status-ok">ONLINE (BKG)</td>
                </tr>
                <tr>
                    <td><span class="glow-text-purple">L'ANGELO CUSTODE</span> 🛡️</td>
                    <td>MEV Protection / Arbitrum</td>
                    <td class="status-ok">ONLINE (BKG)</td>
                </tr>
            </table>
        </div>
        
        <div class="panel" style="grid-column: 1 / -1;">
            <h2 class="glow-text-cyan">📊 METRICHE DI MERCATO STRATEGICHE</h2>
            <hr style="border-color: #0ff; opacity: 0.5;">
            <div style="display: flex; justify-content: space-between; text-align: center; margin-top: 15px;">
                <div class="metric-box" style="border-color: #0ff;">
                    <h3 style="color: #aaa; font-size: 1em;">THE ORACLE (BINANCE) 🔮</h3>
                    <div style="font-size: 2.2em; margin: 10px 0;" class="glow-text-cyan">BULLISH 78%</div>
                    <p style="color: #777; margin:0;">Long/Short Ratio: 1.45</p>
                </div>
                <div class="metric-box" style="border-color: #f00;">
                    <h3 style="color: #aaa; font-size: 1em;">WHALE TRACKER 🐋</h3>
                    <div style="font-size: 2.2em; margin: 10px 0;" class="glow-text-red blink">ALERT</div>
                    <p style="color: #777; margin:0;">+4,500 BTC moved to Exchange</p>
                </div>
                <div class="metric-box" style="border-color: #b0f;">
                    <h3 style="color: #aaa; font-size: 1em;">VOLATILITY INDEX ⚡</h3>
                    <div style="font-size: 2.2em; margin: 10px 0;" class="glow-text-purple">ELEVATED</div>
                    <p style="color: #777; margin:0;">VIX Crypto: 65.2</p>
                </div>
            </div>
        </div>
        
        <div class="header" style="background: rgba(0, 10, 0, 0.95); font-size: 0.85em; padding: 10px; border-width: 1px; color: #555;">
            SYSTEM UPTIME: <span class="status-ok">99.999%</span> | CPU LOAD: <span class="status-warn">74%</span> | MEMORY: <span class="status-ok">32GB / 64GB</span> | NETWORK: <span class="glow-text-cyan">SECURE</span>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Force Flask to run silently in production mode via Waitress if available, else plain Flask
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=5000)
    except ImportError:
        app.run(host='0.0.0.0', port=5000)
