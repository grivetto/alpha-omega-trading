import os
import threading
from flask import Flask, render_template_string

app = Flask(__name__)

# Preserve old print logs for legacy integrations
print("ORBITAL COMMAND - Dashboard Initializing...")
print("⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA]</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: #111;
            --glow-green: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            --glow-blue: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: var(--glow-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 20px;
            margin-bottom: 30px;
            position: relative;
        }
        .header h1 {
            font-size: 3em;
            margin: 0;
            color: var(--neon-blue);
            text-shadow: var(--glow-blue);
            letter-spacing: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green) inset;
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::after {
            content: '';
            position: absolute;
            top: 0; left: -100%; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            font-weight: bold;
        }
        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            font-weight: bold;
            animation: pulse-blue 2s infinite;
        }
        .status-danger {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
            font-weight: bold;
            animation: pulse-red 1s infinite;
        }
        @keyframes pulse-red {
            0%, 100% { opacity: 1; text-shadow: 0 0 5px var(--neon-red); }
            50% { opacity: 0.5; text-shadow: none; }
        }
        @keyframes pulse-blue {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .squad { margin-bottom: 15px; border-left: 4px solid var(--neon-blue); padding-left: 15px; background: rgba(0,255,255,0.05); border-radius: 0 5px 5px 0; padding-top: 5px; padding-bottom: 5px; }
        .squad-trinity { margin-bottom: 15px; border-left: 4px solid var(--neon-pink); padding-left: 15px; background: rgba(255,0,255,0.05); border-radius: 0 5px 5px 0; padding-top: 5px; padding-bottom: 5px; }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .metric-box {
            border: 1px dashed var(--neon-pink);
            padding: 15px;
            text-align: center;
            background: rgba(255,0,255,0.05);
            transition: all 0.3s;
        }
        .metric-box:hover {
            background: rgba(255,0,255,0.1);
            transform: scale(1.02);
        }
        .metric-value {
            font-size: 1.5em;
            margin-top: 10px;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; background: rgba(0,0,0,0.5); }
        th, td { border: 1px solid #333; padding: 10px; text-align: left; }
        th { color: var(--neon-blue); border-bottom: 2px solid var(--neon-blue); }
        tr:hover { background: rgba(0,255,0,0.1); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPTIME: <span id="uptime">99.99%</span> | ENCRYPTION: AES-256 GCM</p>
        <p style="font-size: 1.2em; color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); font-weight: bold; animation: pulse-blue 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- 1) ASSAULT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="squad">
                <h3 style="color: var(--neon-blue);">🐺 SQUADRA_ALPHA</h3>
                <p>Role: Scalper on Binance</p>
                <p>Status: <span class="status-active">ENGAGED</span></p>
                <p>APM: <span id="apm-alpha">145</span> | PNL: <span class="status-online">+4.2% (24h)</span></p>
            </div>
            <div class="squad">
                <h3 style="color: var(--neon-blue);">🦅 SQUADRA_DELTA</h3>
                <p>Role: Order Flow</p>
                <p>Status: <span class="status-active">MONITORING</span></p>
                <p>Imbalance Detected: <span id="imbalance">73% ASK</span></p>
            </div>
            <div class="squad">
                <h3 style="color: var(--neon-blue);">🦂 SQUADRA_GAMMA</h3>
                <p>Role: Pairs Trading on Bitget</p>
                <p>Status: <span class="status-active">ARBITRAGING</span></p>
                <p>Spread: <span id="spread">0.15%</span> (BTC/ETH)</p>
            </div>
        </div>

        <!-- 2) PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">🔺 PROTOCOLLO TRINITY</h2>
            <div class="squad-trinity">
                <h3 style="color: var(--neon-pink);">🕴️ LO STROZZINO</h3>
                <p>Role: Funding Arb</p>
                <p>Status: <span class="status-online">ONLINE IN BACKGROUND</span></p>
                <p>Yield: +0.012% / 8h</p>
            </div>
            <div class="squad-trinity">
                <h3 style="color: var(--neon-pink);">🧮 IL CONTABILE</h3>
                <p>Role: DCA Engine</p>
                <p>Status: <span class="status-online">ONLINE IN BACKGROUND</span></p>
                <p>Next execution: <span id="dca-timer">14m 22s</span></p>
            </div>
            <div class="squad-trinity">
                <h3 style="color: var(--neon-pink);">🛡️ L'ANGELO CUSTODE</h3>
                <p>Role: MEV Arbitrum</p>
                <p>Status: <span class="status-online">ONLINE IN BACKGROUND</span></p>
                <p>Blocks sniped: <span id="mev-blocks">42</span> (24h)</p>
            </div>
        </div>

        <!-- 3) MARKET METRICS -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div style="font-size: 0.9em; font-weight: bold;">👁️ THE ORACLE (Binance Sentiment)</div>
                    <div class="metric-value status-online">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.9em; font-weight: bold;">🐋 WHALE TRACKER</div>
                    <div class="metric-value status-danger">LARGE MOVE DETECTED</div>
                </div>
            </div>
            
            <h3 style="margin-top:25px; font-size:1.1em; color:var(--neon-blue);">📡 Recent Intercepts</h3>
            <table>
                <tr><th>Time</th><th>Asset</th><th>Amount</th><th>Type</th></tr>
                <tr><td id="t1">12:45:02</td><td>BTC</td><td>1,200</td><td><span class="status-danger">SELL</span></td></tr>
                <tr><td id="t2">12:41:15</td><td>ETH</td><td>15,000</td><td><span class="status-online">BUY</span></td></tr>
                <tr><td id="t3">12:30:55</td><td>SOL</td><td>250,000</td><td><span class="status-online">BUY</span></td></tr>
            </table>
        </div>
    </div>
    
    <script>
        // Fake dynamic updates for dashboard feel
        setInterval(() => {
            document.getElementById('apm-alpha').innerText = Math.floor(140 + Math.random() * 20);
            if (Math.random() > 0.7) {
                document.getElementById('imbalance').innerText = Math.floor(65 + Math.random() * 20) + '% ASK';
            }
        }, 2000);
        
        setInterval(() => {
            let b = parseInt(document.getElementById('mev-blocks').innerText);
            if (Math.random() > 0.9) document.getElementById('mev-blocks').innerText = b + 1;
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()
