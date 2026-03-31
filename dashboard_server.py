import os
import json
import time
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --font-family: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: var(--font-family);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue);
            margin-bottom: 40px;
            letter-spacing: 5px;
            animation: glitch 1.5s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }

        .box {
            border: 2px solid var(--neon-green);
            padding: 20px;
            position: relative;
            background: rgba(0, 255, 0, 0.05);
            box-shadow: 0 0 10px var(--neon-green) inset, 0 0 10px var(--neon-green);
            transition: all 0.3s ease;
        }

        .box:hover {
            box-shadow: 0 0 20px var(--neon-green) inset, 0 0 20px var(--neon-green);
            transform: scale(1.02);
        }

        .box.trinity {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            background: rgba(255, 0, 255, 0.05);
            box-shadow: 0 0 10px var(--neon-pink) inset, 0 0 10px var(--neon-pink);
        }
        .box.trinity:hover {
            box-shadow: 0 0 20px var(--neon-pink) inset, 0 0 20px var(--neon-pink);
        }

        .box.market {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            background: rgba(0, 255, 255, 0.05);
            box-shadow: 0 0 10px var(--neon-blue) inset, 0 0 10px var(--neon-blue);
        }
        .box.market:hover {
            box-shadow: 0 0 20px var(--neon-blue) inset, 0 0 20px var(--neon-blue);
        }

        h2 {
            margin-top: 0;
            font-size: 1.5em;
            border-bottom: 1px dashed currentcolor;
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        li {
            margin-bottom: 15px;
            font-size: 1.1em;
            display: flex;
            flex-direction: column;
        }

        .status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            margin-top: 5px;
            font-weight: bold;
            text-shadow: none;
        }

        .status.online { background-color: var(--neon-green); color: black; }
        .status.active { background-color: var(--neon-yellow); color: black; animation: blink 1s infinite; }
        .status.standby { background-color: var(--neon-blue); color: black; }
        .status.deploying { background-color: var(--neon-pink); color: black; animation: blink 0.5s infinite; }

        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }

        .metric-item {
            border: 1px solid currentcolor;
            padding: 10px;
            text-align: center;
            font-size: 0.9em;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            margin-top: 5px;
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.2) 10%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 6s linear infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        
        @keyframes glitch {
            0% { text-shadow: 0 0 10px var(--neon-blue); }
            50% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-blue); }
            100% { text-shadow: 0 0 10px var(--neon-blue); }
        }

        .system-time {
            position: absolute;
            top: 20px;
            right: 20px;
            font-size: 1.2em;
            color: var(--neon-yellow);
        }
        
        .sys-log {
            margin-top: 40px;
            border: 1px solid #333;
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            color: #aaa;
            font-size: 0.9em;
            background: rgba(0,0,0,0.5);
        }
        
        .sys-log p {
            margin: 2px 0;
            animation: slideUp 0.3s ease-out forwards;
        }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="system-time" id="clock">00:00:00 UTC</div>
    
    <h1>[ NUVOLA ORBITAL COMMAND ]</h1>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="box">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span>SQUADRA_ALPHA (Binance Scalper)</span>
                    <span class="status active">ENGAGED - LONG BTC</span>
                    <div class="metrics-grid">
                        <div class="metric-item">Latency<div class="metric-value">12ms</div></div>
                        <div class="metric-item">Win Rate<div class="metric-value">68.4%</div></div>
                    </div>
                </li>
                <li>
                    <span>SQUADRA_DELTA (Order Flow)</span>
                    <span class="status online">SCANNING BOOK</span>
                    <div class="metrics-grid">
                        <div class="metric-item">Spoof Detected<div class="metric-value">0</div></div>
                        <div class="metric-item">Imbalance<div class="metric-value">-1.2%</div></div>
                    </div>
                </li>
                <li>
                    <span>SQUADRA_GAMMA (Bitget Pairs Trading)</span>
                    <span class="status standby">AWAITING SIGNAL</span>
                    <div class="metrics-grid">
                        <div class="metric-item">Spread<div class="metric-value">0.15%</div></div>
                        <div class="metric-item">Z-Score<div class="metric-value">1.1</div></div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="box trinity">
            <h2>⚡ PROTOCOLLO TRINITY</h2>
            <div class="status online" style="display: block; text-align: center; margin-bottom: 15px; font-size: 1.1em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <ul>
                <li>
                    <span>💰 Lo Strozzino (Funding Arb)</span>
                    <span class="status online">ONLINE - YIELD FARMING</span>
                    <div class="metrics-grid">
                        <div class="metric-item" style="border-color:var(--neon-pink)">APR<div class="metric-value" style="color:var(--neon-pink)">18.5%</div></div>
                        <div class="metric-item" style="border-color:var(--neon-pink)">Exposure<div class="metric-value" style="color:var(--neon-pink)">Delta-Neutral</div></div>
                    </div>
                </li>
                <li>
                    <span>📈 Il Contabile (DCA Engine)</span>
                    <span class="status online">ONLINE - ACCUMULATING</span>
                    <div class="metrics-grid">
                        <div class="metric-item" style="border-color:var(--neon-pink)">Next Buy<div class="metric-value" style="color:var(--neon-pink)">14h 22m</div></div>
                        <div class="metric-item" style="border-color:var(--neon-pink)">Avg Cost<div class="metric-value" style="color:var(--neon-pink)">$54,210</div></div>
                    </div>
                </li>
                <li>
                    <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                    <span class="status deploying">PROWLING MEMPOOL</span>
                    <div class="metrics-grid">
                        <div class="metric-item" style="border-color:var(--neon-pink)">Blocks Scanned<div class="metric-value" style="color:var(--neon-pink)" id="blocks">1,024,192</div></div>
                        <div class="metric-item" style="border-color:var(--neon-pink)">Snipes Today<div class="metric-value" style="color:var(--neon-pink)">3</div></div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="box market">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <span>🔮 The Oracle (Binance Sentiment)</span>
                    <span class="status online">PROCESSING NLP</span>
                    <div class="metrics-grid">
                        <div class="metric-item" style="border-color:var(--neon-blue)">Fear & Greed<div class="metric-value" style="color:var(--neon-blue)">72 (GREED)</div></div>
                        <div class="metric-item" style="border-color:var(--neon-blue)">Trend Bias<div class="metric-value" style="color:var(--neon-blue)">BULLISH</div></div>
                    </div>
                </li>
                <li>
                    <span>🐋 Whale Tracker</span>
                    <span class="status active">TRACKING LARGE TXS</span>
                    <div class="metrics-grid">
                        <div class="metric-item" style="border-color:var(--neon-blue)">Inflow (24h)<div class="metric-value" style="color:var(--neon-blue)">+$45M</div></div>
                        <div class="metric-item" style="border-color:var(--neon-blue)">Alerts<div class="metric-value" style="color:var(--neon-red)">1 TRIGGERED</div></div>
                    </div>
                </li>
            </ul>
        </div>
    </div>
    
    <div class="sys-log" id="syslog">
        <p>> NUVOLA ORBITAL COMMAND INITIALIZED...</p>
        <p>> SECURE CONNECTION ESTABLISHED...</p>
    </div>

    <script>
        // Clock update
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Fake MEV block counter
        let blocks = 1024192;
        setInterval(() => {
            blocks += Math.floor(Math.random() * 3);
            document.getElementById('blocks').innerText = blocks.toLocaleString();
        }, 2000);

        // Fake Syslog
        const logs = [
            "> [ALPHA] Executing limit order #9982...",
            "> [THE ORACLE] Twitter sentiment shift detected: +0.4",
            "> [ANGELO] Mempool congestion moderate. Adjusting gas...",
            "> [WHALE TRACKER] 1,000 BTC transferred from unknown to Binance",
            "> [STROZZINO] Funding rate inverted on Bybit. Rebalancing...",
            "> [DELTA] Spoofing wall at $70,000 withdrawn.",
            "> [SYSTEM] Heartbeat OK."
        ];
        
        setInterval(() => {
            const logBox = document.getElementById('syslog');
            const newLog = document.createElement('p');
            newLog.innerText = logs[Math.floor(Math.random() * logs.length)];
            logBox.appendChild(newLog);
            if(logBox.children.length > 6) {
                logBox.removeChild(logBox.firstChild);
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
