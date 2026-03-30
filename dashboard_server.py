import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --bg: #050510;
            --text-main: #00ffcc;
            --text-alert: #ff0055;
            --text-warn: #ffcc00;
            --text-ok: #33ff33;
            --border: #00ffcc;
            --glow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
            --glow-alert: 0 0 10px #ff0055, 0 0 20px #ff0055;
        }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 204, .05) 25%, rgba(0, 255, 204, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, .05) 75%, rgba(0, 255, 204, .05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 204, .05) 25%, rgba(0, 255, 204, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, .05) 75%, rgba(0, 255, 204, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            margin-top: 0;
            text-shadow: var(--glow);
            letter-spacing: 2px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 5px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--border);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 4s infinite;
        }
        .header h1 { border: none; }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            border: 1px solid var(--border);
            background: rgba(0, 255, 204, 0.05);
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0,255,204,0.1);
            position: relative;
            backdrop-filter: blur(2px);
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: inset 0 0 25px rgba(0,255,204,0.3), 0 0 10px var(--border);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 10px; height: 10px;
            border-top: 2px solid var(--border);
            border-left: 2px solid var(--border);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 10px; height: 10px;
            border-bottom: 2px solid var(--border);
            border-right: 2px solid var(--border);
        }
        .status-ok { color: var(--text-ok); text-shadow: 0 0 5px var(--text-ok); }
        .status-warn { color: var(--text-warn); text-shadow: 0 0 5px var(--text-warn); }
        .status-alert { color: var(--text-alert); text-shadow: var(--glow-alert); }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 12px; border-bottom: 1px dashed rgba(0,255,204,0.3); padding-bottom: 8px;}
        li:last-child { border: none; }
        
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; }
        }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .data-stream {
            margin-top: 15px;
            font-size: 0.85em;
            color: rgba(0, 255, 204, 0.8);
            height: 80px;
            overflow: hidden;
            background: rgba(0,0,0,0.5);
            padding: 5px;
            border-radius: 2px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1><span class="blink">🔴</span> ORBITAL COMMAND UPLINK</h1>
        <p>NUVOLA TACTICAL DASHBOARD v3.1 | SYS.TIME: <span id="clock"></span> | AUTH: ROOT</p>
        <p style="color: var(--text-ok); font-weight: bold; text-shadow: 0 0 5px var(--text-ok);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- 1. SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>SQUADRA_ALPHA</strong> [Binance Scalper]<br>
                    Status: <span class="status-ok">ENGAGED</span> | PNL: <span class="status-ok">+4.2%</span> | Latency: 12ms
                </li>
                <li><strong>SQUADRA_DELTA</strong> [Order Flow]<br>
                    Status: <span class="status-warn">STANDBY</span> | Trend: NEUTRAL | APM: 0
                </li>
                <li><strong>SQUADRA_GAMMA</strong> [Bitget Pairs Trading]<br>
                    Status: <span class="status-ok">ACTIVE</span> | Spread: 0.05% | Hedged: YES
                </li>
            </ul>
        </div>

        <!-- 2. PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>LO STROZZINO</strong> [Funding Arb]<br>
                    Status: <span class="status-ok">BACKGROUND ONLINE</span> | APR: <span class="status-ok">18.4%</span>
                </li>
                <li><strong>IL CONTABILE</strong> [DCA Bot]<br>
                    Status: <span class="status-ok">BACKGROUND ONLINE</span> | Next Buy: 4h 12m
                </li>
                <li><strong>L'ANGELO CUSTODE</strong> [MEV Arbitrum]<br>
                    Status: <span class="status-alert blink">HUNTING</span> | Mempool: Scanning...
                </li>
            </ul>
        </div>

        <!-- 3. METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <ul>
                <li><strong>THE ORACLE</strong> [Binance Sentiment]<br>
                    Index: <span class="status-warn">68 (GREED)</span> | Signals: <span class="status-ok">LONG</span>
                </li>
                <li><strong>WHALE TRACKER</strong> [On-Chain Radar]<br>
                    Alert: <span class="status-alert">12,000 BTC moved to Coinbase</span>
                </li>
            </ul>
            <div class="data-stream" id="stream">
                [SYS] STREAM INIT...<br>
            </div>
        </div>
    </div>

    <script>
        // Update Time
        function updateClock() {
            document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').substr(0, 19) + ' UTC';
        }
        setInterval(updateClock, 1000);
        updateClock();
        
        // Fake Terminal Stream
        const stream = document.getElementById('stream');
        const messages = [
            "0x4aB... bought 150 ETH",
            "Liquidating short on SOL-PERP ($450k)",
            "Arbitrum gas fee spike detected (12 gwei)",
            "Binance orderbook imbalance: 62% BUY",
            "New block minted #19583021",
            "Whale Tracker: 5M USDT transferred to Bitget",
            "Oracle: Funding rate turned negative on DOGE"
        ];
        setInterval(() => {
            const msg = messages[Math.floor(Math.random() * messages.length)];
            const timeStr = new Date().toISOString().substr(11, 8);
            stream.innerHTML = `[${timeStr}] ${msg}<br>` + stream.innerHTML;
        }, 2200);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on 0.0.0.0 and arbitrary port so it's accessible.
    app.run(host='0.0.0.0', port=5001)
