import os
import threading
from flask import Flask, render_template_string

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
            --neon-blue: #0ff;
            --neon-red: #ff073a;
            --neon-purple: #b026ff;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image:
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
            animation: pulse 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.trinity { border-color: var(--neon-purple); }
        .panel.trinity::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .panel.metrics { border-color: var(--neon-blue); }
        .panel.metrics::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }

        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-standby { color: #ffa500; text-shadow: 0 0 5px #ffa500; }
        .status-alert { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); animation: blink 1s infinite; }

        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(57, 255, 20, 0.3); padding-bottom: 10px; }

        @keyframes blink { 50% { opacity: 0.5; } }
        @keyframes pulse { 0% { text-shadow: 0 0 10px var(--neon-blue); } 50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); } 100% { text-shadow: 0 0 10px var(--neon-blue); } }
        @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(57, 255, 20, 0.1);
            opacity: 0.5;
            animation: scanline 6s linear infinite;
            pointer-events: none;
            z-index: 999;
        }

        .metric-bar { height: 10px; background: #222; margin-top: 5px; border-radius: 2px; overflow: hidden; }
        .metric-fill { height: 100%; background: var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM STATUS: <span class="status-online">OPTIMAL</span> | UPTIME: 99.9% | ENCRYPTION: MIL-SPEC</p>
        <p style="color: var(--neon-purple); font-weight: bold; border: 1px solid var(--neon-purple); padding: 8px; display: inline-block; box-shadow: 0 0 10px var(--neon-purple); background: rgba(176, 38, 255, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-green);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Binance Scalper]<br>
                    Status: <span class="status-online">ENGAGING</span><br>
                    Win Rate: 68.4% | Ping: 12ms
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow]<br>
                    Status: <span class="status-standby">MONITORING LOB</span><br>
                    Imbalance: +4.2% Bullish
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Bitget Pairs Trading]<br>
                    Status: <span class="status-online">ARBITRAGE ACTIVE</span><br>
                    Spread: 0.15% | Volume: $1.2M
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 style="color: var(--neon-purple);">🔮 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> [Funding Arb]<br>
                    Status: <span class="status-online">EXTRACTING YIELD</span><br>
                    <span style="font-size: 0.8em; color: #ccc;">Short Perpetuals vs Spot Target APY: 18.5%</span>
                </li>
                <li>
                    <strong>Il Contabile</strong> [DCA]<br>
                    Status: <span class="status-online">ACCUMULATING</span><br>
                    <span style="font-size: 0.8em; color: #ccc;">Next Execution: 14:00 UTC | Asset: BTC/ETH</span>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> [Arbitrum MEV]<br>
                    Status: <span class="status-standby">PATROLLING MEMPOOL</span><br>
                    <span style="font-size: 0.8em; color: #ccc;">Flashbots: Ready | Latency: 4ms</span>
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel metrics">
            <h2 style="color: var(--neon-blue);">📊 MARKET METRICS</h2>
            <ul>
                <li>
                    <strong>The Oracle</strong> [Binance Sentiment]<br>
                    Fear/Greed: 65 (GREED)
                    <div class="metric-bar"><div class="metric-fill" style="width: 65%; background: var(--neon-green);"></div></div>
                </li>
                <li>
                    <strong>Whale Tracker</strong> [On-Chain Alerts]<br>
                    Large TX Volume (24h): <span class="status-alert">ELEVATED</span>
                    <div class="metric-bar"><div class="metric-fill" style="width: 85%; background: var(--neon-red);"></div></div>
                </li>
                <li>
                    <strong>Global Liquidity</strong><br>
                    Stablecoin Flow: +$450M Inflow
                    <div class="metric-bar"><div class="metric-fill" style="width: 70%;"></div></div>
                </li>
            </ul>
        </div>
    </div>
    <div style="text-align: center; margin-top: 40px; font-size: 0.8em; color: #444;">
        &copy; 2026 QUANTITATIVE ASSAULT PROTOCOL // UNAUTHORIZED ACCESS FATAL
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Ensure it binds to all interfaces for access
    app.run(host='0.0.0.0', port=5000)
