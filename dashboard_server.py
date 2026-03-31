from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f3;
            --neon-blue: #0ff;
            --neon-red: #f03;
            --bg-color: #050505;
            --panel-bg: rgba(0, 255, 0, 0.02);
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 40px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(0, 255, 51, 0.2), inset 0 0 15px rgba(0, 255, 51, 0.1);
            padding: 20px;
            position: relative;
            border-radius: 5px;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        h2 {
            color: var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-green);
            display: flex;
            justify-content: space-between;
        }

        .status {
            color: var(--neon-blue);
            animation: blink 1.5s infinite;
        }

        .item {
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-green);
            transition: all 0.3s ease;
        }

        .item:hover {
            border-left: 3px solid var(--neon-blue);
            box-shadow: inset 20px 0 20px -20px var(--neon-blue);
            transform: translateX(5px);
        }

        .metric {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            font-size: 0.9em;
        }

        .value {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .value.alert {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .scan-line {
            position: fixed;
            top: 0; left: 0; right: 0;
            height: 5px;
            background: rgba(0, 255, 255, 0.3);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
            animation: scan 6s linear infinite;
            pointer-events: none;
            z-index: 1000;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        @keyframes scan {
            0% { top: -10px; }
            100% { top: 100vh; }
        }

        .terminal-text {
            color: #888;
            font-size: 0.8em;
            margin-top: 20px;
            border-top: 1px solid #333;
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    
    <h1>🛰️ ORBITAL COMMAND | NUVOLA SECURE LINK</h1>

    <div style="text-align: center; margin-bottom: 30px; font-size: 1.5em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); border: 1px solid var(--neon-green); padding: 10px; background: rgba(0,255,0,0.1); border-radius: 5px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span class="status">[DEPLOYED]</span></h2>
            <div class="item">
                <div><strong>SQUADRA_ALPHA</strong> 🦅</div>
                <div class="metric"><span>Target:</span> <span class="value">Binance Scalper</span></div>
                <div class="metric"><span>Status:</span> <span class="value">ONLINE - 1420 TPS</span></div>
                <div class="metric"><span>Win Rate:</span> <span class="value">68.4%</span></div>
            </div>
            <div class="item">
                <div><strong>SQUADRA_DELTA</strong> 🌊</div>
                <div class="metric"><span>Target:</span> <span class="value">Order Flow / Liquidations</span></div>
                <div class="metric"><span>Status:</span> <span class="value">SCANNING BOOKS</span></div>
                <div class="metric"><span>Depth:</span> <span class="value">L2 Active</span></div>
            </div>
            <div class="item">
                <div><strong>SQUADRA_GAMMA</strong> ⚖️</div>
                <div class="metric"><span>Target:</span> <span class="value">Pairs Trading (Bitget)</span></div>
                <div class="metric"><span>Status:</span> <span class="value">SYNCED</span></div>
                <div class="metric"><span>Spread:</span> <span class="value">0.15%</span></div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY <span class="status">[ACTIVE]</span></h2>
            <div class="item">
                <div><strong>Lo Strozzino</strong> 🕴️</div>
                <div class="metric"><span>Role:</span> <span class="value">Funding Arbitrage</span></div>
                <div class="metric"><span>Status:</span> <span class="value">EXTRACTING YIELD</span></div>
                <div class="metric"><span>Est. APR:</span> <span class="value">24.5%</span></div>
            </div>
            <div class="item">
                <div><strong>Il Contabile</strong> 🧮</div>
                <div class="metric"><span>Role:</span> <span class="value">DCA & Rebalancing</span></div>
                <div class="metric"><span>Status:</span> <span class="value">ACCUMULATING</span></div>
                <div class="metric"><span>Next Buy:</span> <span class="value">14h 22m</span></div>
            </div>
            <div class="item">
                <div><strong>L'Angelo Custode</strong> 🛡️</div>
                <div class="metric"><span>Role:</span> <span class="value">MEV Protection (Arbitrum)</span></div>
                <div class="metric"><span>Status:</span> <span class="value">GUARDING MEMPOOL</span></div>
                <div class="metric"><span>Threats Blocked:</span> <span class="value">12</span></div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO <span class="status">[LIVE]</span></h2>
            <div class="item">
                <div><strong>The Oracle</strong> 👁️</div>
                <div class="metric"><span>Source:</span> <span class="value">Binance Sentiment Net</span></div>
                <div class="metric"><span>Bias:</span> <span class="value" style="color: var(--neon-green)">BULLISH (78%)</span></div>
                <div class="metric"><span>Volatility Index:</span> <span class="value">MEDIUM</span></div>
            </div>
            <div class="item">
                <div><strong>Whale Tracker</strong> 🐳</div>
                <div class="metric"><span>Scan Area:</span> <span class="value">ERC-20 & TRC-20</span></div>
                <div class="metric"><span>Alerts:</span> <span class="value alert">3 MASSIVE TX DETECTED</span></div>
                <div class="metric"><span>Largest Move:</span> <span class="value alert">14,500 ETH -> Coinbase</span></div>
            </div>
            <div class="item">
                <div><strong>System Health</strong> 💻</div>
                <div class="metric"><span>Latency:</span> <span class="value">14ms</span></div>
                <div class="metric"><span>Memory Usage:</span> <span class="value">42%</span></div>
                <div class="metric"><span>Uptime:</span> <span class="value">99.999%</span></div>
            </div>
        </div>
    </div>

    <div class="terminal-text">
        <p>> INITIALIZING SECURE HANDSHAKE... OK.</p>
        <p>> LOADING NUVOLA PROTOCOLS... OK.</p>
        <p>> ORBITAL COMMAND IS WATCHING. ALL SYSTEMS NOMINAL.</p>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000 by default, accessible on all interfaces
    app.run(host='0.0.0.0', port=5000, threaded=True)
