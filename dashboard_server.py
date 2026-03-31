import os
from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --bg: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --grid-color: rgba(0, 243, 255, 0.1);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image:
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            letter-spacing: 2px;
        }
        h1 { text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            border: 1px solid var(--neon-blue);
            background: rgba(0, 20, 40, 0.6);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2) inset;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: var(--neon-blue);
            animation: scanline 4s linear infinite;
            box-shadow: 0 0 10px var(--neon-blue);
        }
        @keyframes scanline {
            100% { left: 200%; }
        }
        .status {
            float: right;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
        }
        .status.standby {
            color: #ffaa00;
            text-shadow: 0 0 5px #ffaa00;
        }
        .status.offline {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(0,243,255,0.3); padding-bottom: 5px; }
        .highlight { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .metric { font-size: 1.2em; font-weight: bold; }
        .bar-bg { background: #111; height: 10px; border: 1px solid var(--neon-blue); margin-top: 5px; }
        .bar-fill { height: 100%; background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); transition: width 0.5s; }
        .bar-fill.pink { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .bar-fill.green { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND | NUVOLA CORE 🛰️</h1>
    <div style="text-align: center; color: var(--neon-pink); font-size: 0.9em; margin-bottom: 20px;">
        SYSTEM STATUS: <span class="status" style="float:none;">ONLINE</span> | ENCRYPTION: 256-bit AES | LCY: 12ms
    </div>
    <div style="text-align: center; color: var(--neon-green); font-size: 1.1em; margin-bottom: 20px; font-weight: bold; border: 1px solid var(--neon-green); padding: 10px; background: rgba(57, 255, 20, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong> <span class="status">ACTIVE</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">Target: Binance Scalping | Win Rate: 68.4%</span>
                    <div class="bar-bg"><div class="bar-fill green" style="width: {{ alpha_load }}%;"></div></div>
                </li>
                <li>
                    <strong>🦅 SQUADRA_DELTA</strong> <span class="status">ACTIVE</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">Target: Order Flow Analysis | Imbalance: Bullish</span>
                    <div class="bar-bg"><div class="bar-fill pink" style="width: {{ delta_load }}%;"></div></div>
                </li>
                <li>
                    <strong>🐍 SQUADRA_GAMMA</strong> <span class="status standby">STANDBY</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">Target: Bitget Pairs Trading | Spread: 0.12%</span>
                    <div class="bar-bg"><div class="bar-fill" style="width: 15%;"></div></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-pink);">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🎩 Lo Strozzino</strong> <span class="status">ONLINE</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">Funding Arb: <span class="highlight">APR 24.5%</span></span>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> <span class="status">ONLINE</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">DCA Matrix: Next entry in 4h 12m</span>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> <span class="status">ONLINE</span><br>
                    <span style="font-size: 0.8em; color: #aaa;">MEV Arbitrum: Frontrunning protection engaged</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong>🧠 The Oracle (Binance Sentiment)</strong><br>
                    <span class="metric" style="color: var(--neon-green);">GREED (72/100)</span>
                    <div style="font-size: 0.8em; margin-top: 5px;">Retail Long/Short Ratio: 1.45</div>
                </li>
                <li>
                    <strong>🐋 Whale Tracker</strong><br>
                    <span class="metric highlight">ALERT: 1,450 BTC moved to Coinbase</span>
                    <div style="font-size: 0.8em; margin-top: 5px;">Time: 2m ago | TX: 0x9a8b...f4c2</div>
                </li>
                <li>
                    <strong>🌐 Nuvola Node Latency</strong><br>
                    API Binance: 12ms | API Bitget: 24ms | RPC Arbitrum: 8ms
                </li>
            </ul>
        </div>
    </div>

    <script>
        // Refresh auto per simulare live data
        setTimeout(() => { window.location.reload(); }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        alpha_load=random.randint(40, 95),
        delta_load=random.randint(30, 80)
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
