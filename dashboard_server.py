from flask import Flask, render_template_string
import random
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --panel-bg: rgba(10, 20, 30, 0.85);
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, 0.05) 25%, rgba(0, 255, 0, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.05) 75%, rgba(0, 255, 0, 0.05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 0, 0.05) 25%, rgba(0, 255, 0, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.05) 75%, rgba(0, 255, 0, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2 {
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
            margin-bottom: 30px;
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
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(to right, transparent, rgba(0, 255, 255, 0.1), transparent);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .panel h3 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px solid var(--neon-pink);
            padding-bottom: 10px;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            font-weight: bold;
        }
        .status-standby {
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow);
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9em;
            border-bottom: 1px dashed rgba(0, 255, 0, 0.3);
            padding-bottom: 5px;
        }
        .metric-value {
            color: white;
            text-shadow: 0 0 5px white;
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        .log-box {
            background: #000;
            border: 1px solid var(--neon-green);
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.8em;
            color: var(--neon-green);
            box-shadow: inset 0 0 10px rgba(0,255,0,0.2);
        }
        .log-entry { margin: 5px 0; }
    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2 class="blink" style="font-size: 1.2em; color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">SYSTEM ONLINE - DEFCON 4</h2>
    <h3 style="text-align: center; color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>

    <div class="container">
        <!-- 1) SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            
            <div class="metric-row">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status-online">ENGAGED</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ APY 24h:</span>
                <span class="metric-value" style="color:var(--neon-green)">+12.4%</span>
            </div>
            
            <div class="metric-row">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="status-standby">STANDBY</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ Target:</span>
                <span class="metric-value">Liquidity hunting</span>
            </div>

            <div class="metric-row">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status-online">ACTIVE</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ Spread:</span>
                <span class="metric-value">0.08%</span>
            </div>
        </div>

        <!-- 2) PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-yellow); box-shadow: 0 0 15px rgba(255, 255, 0, 0.2), inset 0 0 10px rgba(255, 255, 0, 0.1);">
            <h3 style="color: var(--neon-yellow); border-color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow);">🔺 PROTOCOLLO TRINITY</h3>
            
            <div class="metric-row">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="status-online">COLLECTING</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ Yield:</span>
                <span class="metric-value">+0.01% / 8h</span>
            </div>
            
            <div class="metric-row">
                <span>💼 Il Contabile (DCA)</span>
                <span class="status-online">ACCUMULATING</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ BTC/ETH:</span>
                <span class="metric-value">Next buy in 4h</span>
            </div>

            <div class="metric-row">
                <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online" style="color: var(--neon-blue);">MONITORING MEMPOOL</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ Frontruns:</span>
                <span class="metric-value">0 today</span>
            </div>
        </div>

        <!-- 3) METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-pink); box-shadow: 0 0 15px rgba(255, 0, 255, 0.2), inset 0 0 10px rgba(255, 0, 255, 0.1);">
            <h3 style="color: var(--neon-blue); border-color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue);">📡 THE ORACLE & WHALES</h3>
            
            <div class="metric-row">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span class="status-online">BULLISH 78%</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ AI Confidence:</span>
                <span class="metric-value">HIGH</span>
            </div>
            
            <div class="metric-row">
                <span>🐋 Whale Tracker</span>
                <span class="status-online blink" style="color: var(--neon-red);">ALERT</span>
            </div>
            <div class="metric-row">
                <span>&nbsp;&nbsp;↳ Latest Move:</span>
                <span class="metric-value" style="color: var(--neon-red)">1200 BTC to Coinbase</span>
            </div>

            <div class="log-box" id="terminal-log">
                <div class="log-entry">> Initializing Quantum Link... OK</div>
                <div class="log-entry">> Syncing with Binance API... OK</div>
                <div class="log-entry">> Connecting to Bitget Nodes... OK</div>
                <div class="log-entry">> Arbitrum Mempool scan active.</div>
                <div class="log-entry blink">> Awaiting further instructions...</div>
            </div>
        </div>
    </div>

    <script>
        // Simple script to fake incoming logs
        const logs = [
            "> Arbitrage opportunity detected (Spread 0.15%)",
            "> SQUADRA_ALPHA executed BUY 0.5 BTC at Market",
            "> The Oracle sentiment shifted to 79%",
            "> Il Contabile verifying fiat reserves...",
            "> L'Angelo Custode: Gas spike on Arbitrum! Holding...",
            "> Lo Strozzino received funding fee: +0.005 USDT",
            "> Whale Tracker: 50M USDT minted at Tether Treasury"
        ];
        
        setInterval(() => {
            const logBox = document.getElementById('terminal-log');
            const newLog = document.createElement('div');
            newLog.className = 'log-entry';
            newLog.innerText = logs[Math.floor(Math.random() * logs.length)];
            logBox.appendChild(newLog);
            if(logBox.children.length > 7) {
                logBox.removeChild(logBox.children[0]);
            }
        }, 4000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
