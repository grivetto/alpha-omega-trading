from flask import Flask, render_template_string
import threading
import time
import psutil
import os

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
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
            --border-color: rgba(57, 255, 20, 0.4);
        }
        
        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(57, 255, 20, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(57, 255, 20, 0.03) 1px, transparent 1px);
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
            padding: 20px;
            border-bottom: 2px solid var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-green); }
            50% { text-shadow: 0 0 20px var(--neon-green), 0 0 30px var(--neon-green); }
            100% { text-shadow: 0 0 5px var(--neon-green); }
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 20px;
            position: relative;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.8), 0 0 10px var(--border-color);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 15px rgba(0,0,0,0.9), 0 0 20px var(--neon-blue);
            border-color: var(--neon-blue);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 10px; height: 10px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }

        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            border-bottom: 1px solid rgba(0, 243, 255, 0.3);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1s infinite;
        }

        .status-offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 8px var(--neon-red);
            animation: none;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 243, 255, 0.05);
            border-left: 3px solid var(--neon-blue);
        }

        .metric {
            display: flex;
            justify-content: space-between;
            font-size: 0.9em;
            margin-top: 5px;
            color: #aaa;
        }

        .highlight {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }

        .scrolling-text {
            overflow: hidden;
            white-space: nowrap;
            box-sizing: border-box;
            border-top: 1px solid var(--neon-red);
            border-bottom: 1px solid var(--neon-red);
            padding: 5px 0;
            margin-top: 30px;
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .scrolling-text p {
            display: inline-block;
            padding-left: 100%;
            animation: scroll 20s linear infinite;
            margin: 0;
        }

        @keyframes scroll {
            0% { transform: translate(0, 0); }
            100% { transform: translate(-100%, 0); }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        th, td {
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid rgba(57, 255, 20, 0.2);
        }
        
        th {
            color: var(--neon-blue);
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM STATUS: <span style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">ONLINE</span> | SECURE CONNECTION ESTABLISHED</p>
        <h3 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); margin-top: 15px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🦅 SQUADRA_ALPHA</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Type:</span> <span class="highlight">Binance Scalper</span></div>
                    <div class="metric"><span>Target:</span> <span>BTC/USDT, ETH/USDT</span></div>
                    <div class="metric"><span>Status:</span> <span style="color: var(--neon-green)">Engaged</span></div>
                </li>
                <li>
                    <strong>🐺 SQUADRA_DELTA</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Type:</span> <span class="highlight">Order Flow</span></div>
                    <div class="metric"><span>Target:</span> <span>SOL/USDT</span></div>
                    <div class="metric"><span>Status:</span> <span style="color: var(--neon-green)">Monitoring Orderbook</span></div>
                </li>
                <li>
                    <strong>🐍 SQUADRA_GAMMA</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Type:</span> <span class="highlight">Pairs Trading</span></div>
                    <div class="metric"><span>Exchange:</span> <span>Bitget</span></div>
                    <div class="metric"><span>Status:</span> <span style="color: var(--neon-green)">Calculating Spread</span></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Role:</span> <span class="highlight">Funding Arbitrage</span></div>
                    <div class="metric"><span>Yield Rate:</span> <span style="color: var(--neon-green)">+14.2% APR</span></div>
                    <div class="metric"><span>Active Positions:</span> <span>3</span></div>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Role:</span> <span class="highlight">DCA Engine</span></div>
                    <div class="metric"><span>Next Buy:</span> <span>04:12:30</span></div>
                    <div class="metric"><span>Accumulated:</span> <span>0.15 BTC</span></div>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> <span class="status-indicator"></span>
                    <div class="metric"><span>Role:</span> <span class="highlight">MEV Arbitrum</span></div>
                    <div class="metric"><span>Mempool:</span> <span style="color: var(--neon-green)">Scanning</span></div>
                    <div class="metric"><span>Last Snipe:</span> <span>2 mins ago</span></div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 15px;">
                <strong>🔮 The Oracle (Binance Sentiment)</strong>
                <table>
                    <tr><th>Asset</th><th>Signal</th><th>Confidence</th></tr>
                    <tr><td>BTC</td><td style="color: var(--neon-green)">BULLISH</td><td>87%</td></tr>
                    <tr><td>ETH</td><td style="color: var(--neon-green)">BULLISH</td><td>75%</td></tr>
                    <tr><td>SOL</td><td style="color: var(--neon-red)">BEARISH</td><td>62%</td></tr>
                </table>
            </div>
            <div>
                <strong>🐋 Whale Tracker</strong>
                <table>
                    <tr><th>Time</th><th>Action</th><th>Volume</th></tr>
                    <tr><td>14:32</td><td>Inflow</td><td>500 BTC</td></tr>
                    <tr><td>14:28</td><td style="color: var(--neon-red)">Outflow</td><td>12,000 ETH</td></tr>
                    <tr><td>14:15</td><td>Swap</td><td>5M USDC</td></tr>
                </table>
            </div>
        </div>
        
        <!-- SYSTEM RESOURCES -->
        <div class="panel">
            <h2>💻 SYSTEM DIAGNOSTICS</h2>
            <ul>
                <li>
                    <strong>CPU Usage</strong>
                    <div class="metric"><span>Core 0:</span> <span style="color: var(--neon-green)">12%</span></div>
                    <div class="metric"><span>Core 1:</span> <span style="color: var(--neon-green)">18%</span></div>
                </li>
                <li>
                    <strong>Memory</strong>
                    <div class="metric"><span>Allocated:</span> <span style="color: var(--neon-blue)">4.2 GB</span></div>
                    <div class="metric"><span>Available:</span> <span>11.8 GB</span></div>
                </li>
                <li>
                    <strong>Network Latency</strong>
                    <div class="metric"><span>Binance API:</span> <span style="color: var(--neon-green)">12ms</span></div>
                    <div class="metric"><span>Bitget API:</span> <span style="color: var(--neon-green)">18ms</span></div>
                </li>
            </ul>
        </div>

    </div>

    <div class="scrolling-text">
        <p>⚠️ ALERT: HIGH VOLATILITY DETECTED ON SOLANA NETWORK // SQUADRA_DELTA DEPLOYING ADDITIONAL LIQUIDITY // PROTOCOLLO TRINITY OPERATING AT OPTIMAL CAPACITY // NO CRITICAL ERRORS LOGGED ⚠️</p>
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
