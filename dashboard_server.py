from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 3s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
        }
        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            font-size: 1.2em;
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-standby {
            color: #ff0;
            font-weight: bold;
            text-shadow: 0 0 5px #ff0;
        }
        .item {
            margin: 10px 0;
            padding: 5px;
            border-left: 2px solid var(--neon-pink);
            background: rgba(255, 0, 255, 0.05);
        }
        .item-title {
            color: var(--neon-pink);
            text-shadow: 0 0 3px var(--neon-pink);
            font-weight: bold;
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 22%, 24%, 55% { opacity: 0.8; text-shadow: none; }
        }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .metric-box {
            border: 1px solid #444;
            padding: 10px;
            text-align: center;
            background: #0a0a0a;
        }
        .metric-val {
            font-size: 1.5em;
            color: var(--neon-green);
        }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPLINK: SECURE</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span class="item-title">🦅 SQUADRA_ALPHA</span><br>
                Role: Scalper on Binance<br>
                Status: <span class="status-online">ACTIVE</span> | Latency: 12ms
            </div>
            <div class="item">
                <span class="item-title">🎯 SQUADRA_DELTA</span><br>
                Role: Order Flow Analysis<br>
                Status: <span class="status-online">SCANNING</span> | Depth: 500 levels
            </div>
            <div class="item">
                <span class="item-title">⚖️ SQUADRA_GAMMA</span><br>
                Role: Pairs Trading on Bitget<br>
                Status: <span class="status-standby">AWAITING ARB</span> | Spread: 0.02%
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>💠 PROTOCOLLO TRINITY</h2>
            <p class="status-online blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <p>Background Daemons Online</p>
            <div class="item">
                <span class="item-title">🎩 Lo Strozzino</span><br>
                Strategy: Funding Rate Arbitrage<br>
                Yield: <span class="status-online">+14.2% APY</span>
            </div>
            <div class="item">
                <span class="item-title">🧮 Il Contabile</span><br>
                Strategy: Smart DCA<br>
                Next Buy: In 4h 12m
            </div>
            <div class="item">
                <span class="item-title">🛡️ L'Angelo Custode</span><br>
                Strategy: MEV Protection Arbitrum<br>
                Blocks Checked: 14,204,112
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>The Oracle (Binance)</div>
                    <div class="metric-val">BULLISH</div>
                    <div>Sentiment Score: 78/100</div>
                </div>
                <div class="metric-box">
                    <div>Whale Tracker</div>
                    <div class="metric-val">+$412M</div>
                    <div>Net Inflow (24h)</div>
                </div>
                <div class="metric-box">
                    <div>Global Volatility</div>
                    <div class="metric-val">ELEVATED</div>
                    <div>VIX Crypto: 65.4</div>
                </div>
                <div class="metric-box">
                    <div>Network Fee</div>
                    <div class="metric-val">12 Gwei</div>
                    <div>ETH Mainnet</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Starting Nuvola Orbital Command Dashboard...")
    app.run(host='0.0.0.0', port=5000, debug=False)
