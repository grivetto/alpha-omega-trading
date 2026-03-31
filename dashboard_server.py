from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px currentColor;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 20px;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green));
            animation: scan 3s linear infinite;
        }
        @keyframes scan {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .magenta { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); border-color: var(--neon-magenta); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); }
        .magenta::before { background: linear-gradient(90deg, transparent, var(--neon-magenta)); }
        .cyan { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); border-color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0, 255, 255, 0.2); }
        .cyan::before { background: linear-gradient(90deg, transparent, var(--neon-cyan)); }
        
        .status-online { color: var(--neon-green); animation: blink 1.5s infinite; }
        .status-bg { color: #888; font-style: italic; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 10px; }
        li:last-child { border-bottom: none; }
        .metric-val { float: right; font-weight: bold; }
        small { color: #aaa; display: block; margin-top: 5px; }
        .glitch { position: relative; display: inline-block; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA TERMINAL 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPLINK: SECURE | ENCRYPTION: MIL-SPEC</p>
        <div style="margin-top: 10px; padding: 10px; border: 1px solid var(--neon-magenta); color: var(--neon-magenta); display: inline-block; box-shadow: 0 0 10px rgba(255, 0, 255, 0.4);">
            <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
        </div>
    </div>

    <div class="grid">
        <!-- ASSAULT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>🐺 <b>SQUADRA_ALPHA</b> <span class="metric-val status-online">ACTIVE</span><br><small>Scalper su Binance</small></li>
                <li>🎯 <b>SQUADRA_DELTA</b> <span class="metric-val status-online">ACTIVE</span><br><small>Order Flow</small></li>
                <li>⚖️ <b>SQUADRA_GAMMA</b> <span class="metric-val status-online">ACTIVE</span><br><small>Pairs Trading (Bitget)</small></li>
            </ul>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel magenta">
            <h2 class="magenta">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>🕴️ <b>Lo Strozzino</b> <span class="metric-val status-bg">BACKGROUND</span><br><small>Funding Arb Engine</small></li>
                <li>🧮 <b>Il Contabile</b> <span class="metric-val status-bg">BACKGROUND</span><br><small>DCA / Accumulation</small></li>
                <li>👼 <b>L'Angelo Custode</b> <span class="metric-val status-bg">BACKGROUND</span><br><small>MEV Arbitrum Shield</small></li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel cyan">
            <h2 class="cyan">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>👁️ <b>The Oracle</b> <span class="metric-val">{{ oracle_val }}% BULLISH</span><br><small>Binance Sentiment Analysis</small></li>
                <li>🐋 <b>Whale Tracker</b> <span class="metric-val">{{ whale_val }} BTC</span><br><small>24h Flow Imbalance</small></li>
                <li>⚡ <b>Core Latency</b> <span class="metric-val">{{ latency }} ms</span><br><small>Ping to Match Engine</small></li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    oracle_val = random.randint(55, 88)
    whale_val = random.randint(1200, 8500)
    latency = random.randint(8, 24)
    return render_template_string(HTML_TEMPLATE, oracle_val=oracle_val, whale_val=whale_val, latency=latency)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
