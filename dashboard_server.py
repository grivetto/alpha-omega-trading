from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #00ff66;
            --neon-red: #ff3333;
            --neon-yellow: #ffcc00;
            --text-main: #e0e0e0;
            --panel-bg: rgba(10, 15, 30, 0.8);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
            100% { text-shadow: 0 0 10px var(--neon-blue); }
        }

        .grid-container {
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
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }

        .panel.pink { border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255, 0, 234, 0.3); }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }
        
        .panel.green { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(0, 255, 102, 0.3); }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green); }

        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 8px currentColor;
        }

        .status-online { color: var(--neon-green); background-color: var(--neon-green); animation: blink 1s infinite; }
        .status-standby { color: var(--neon-yellow); background-color: var(--neon-yellow); }
        .status-offline { color: var(--neon-red); background-color: var(--neon-red); }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding: 8px 0;
            font-size: 0.9em;
        }

        .value-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .value-down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .value-neutral { color: var(--neon-blue); }

        .glitch-text {
            position: relative;
            display: inline-block;
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,243,255,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 6s linear infinite;
        }

        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100vh; }
        }

        .terminal-log {
            font-size: 0.8em;
            color: var(--neon-green);
            background: rgba(0,0,0,0.5);
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            border-left: 2px solid var(--neon-green);
        }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <h3>[ NUVOLA TACTICAL DASHBOARD v3.0 ]</h3>
        <p>SYSTEM STATUS: <span class="value-up">ONLINE</span> | UPLINK: <span class="value-neutral">SECURE</span> | LATENCY: 12ms</p>
        <p style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-online"></span> SQUADRA_ALPHA (Binance Scalper)</h4>
                <div class="data-row"><span>Target:</span> <span class="value-neutral">BTC/USDT | ETH/USDT</span></div>
                <div class="data-row"><span>Order Rate:</span> <span class="value-neutral">45/sec</span></div>
                <div class="data-row"><span>Current PnL (1h):</span> <span class="value-up">+ $142.50</span></div>
            </div>

            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-online"></span> SQUADRA_DELTA (Order Flow)</h4>
                <div class="data-row"><span>Target:</span> <span class="value-neutral">Altcoin Momentum</span></div>
                <div class="data-row"><span>Imbalance Detected:</span> <span class="value-up">SOL, INJ</span></div>
                <div class="data-row"><span>Positions:</span> <span class="value-neutral">2 Active</span></div>
            </div>

            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-standby"></span> SQUADRA_GAMMA (Bitget Pairs)</h4>
                <div class="data-row"><span>Target:</span> <span class="value-neutral">Stat Arb</span></div>
                <div class="data-row"><span>Spread:</span> <span class="value-down">Below Threshold (0.12%)</span></div>
                <div class="data-row"><span>Action:</span> <span class="value-neutral">Awaiting Divergence</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink);">🛡️ PROTOCOLLO TRINITY</h2>
            
            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-online"></span> LO STROZZINO (Funding Arb)</h4>
                <div class="data-row"><span>Venue:</span> <span class="value-neutral">Binance vs Bybit</span></div>
                <div class="data-row"><span>Target Yield:</span> <span class="value-up">24.5% APY</span></div>
                <div class="data-row"><span>Deployed Capital:</span> <span class="value-neutral">$15,000</span></div>
            </div>

            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-online"></span> IL CONTABILE (DCA)</h4>
                <div class="data-row"><span>Strategy:</span> <span class="value-neutral">Smart Accumulation</span></div>
                <div class="data-row"><span>Next Buy:</span> <span class="value-neutral">In 4h 12m</span></div>
                <div class="data-row"><span>Avg Price BTC:</span> <span class="value-neutral">$61,240</span></div>
            </div>

            <div style="margin-top: 15px;">
                <h4><span class="status-dot status-online"></span> L'ANGELO CUSTODE (Arbitrum MEV)</h4>
                <div class="data-row"><span>Network:</span> <span class="value-neutral">Arbitrum One</span></div>
                <div class="data-row"><span>Mempool Scanning:</span> <span class="value-up">Active</span></div>
                <div class="data-row"><span>Last Flashloan:</span> <span class="value-neutral">14 mins ago (+$12.40)</span></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green);">👁️ THE ORACLE & WHALE TRACKER</h2>
            
            <div style="margin-top: 15px;">
                <h4>🔮 THE ORACLE (Binance Sentiment)</h4>
                <div class="data-row"><span>Global Sentiment:</span> <span class="value-up">BULLISH (68%)</span></div>
                <div class="data-row"><span>Long/Short Ratio:</span> <span class="value-neutral">1.45</span></div>
                <div class="data-row"><span>Fear & Greed:</span> <span class="value-up">72 (Greed)</span></div>
            </div>

            <div style="margin-top: 15px;">
                <h4>🐋 WHALE TRACKER</h4>
                <div class="data-row"><span>Alert #8842:</span> <span class="value-down">1,500 BTC Transferred to Coinbase</span></div>
                <div class="data-row"><span>Alert #8843:</span> <span class="value-up">50,000,000 USDT Minted (Tether Treasury)</span></div>
                <div class="data-row"><span>Alert #8844:</span> <span class="value-neutral">Large DEX Swap: 2M USDC -> WETH</span></div>
            </div>

            <div style="margin-top: 25px;">
                <h4 style="margin-bottom: 5px;">> TERMINAL LOG_</h4>
                <div class="terminal-log" id="log-container">
                    > [SYS] Initializing Orbital Command... OK<br>
                    > [NET] Connecting to Exchange APIs... SECURE<br>
                    > [HFT] SQUADRA_ALPHA deployed.<br>
                    > [MEV] Listening to Arbitrum Mempool...<br>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Fake terminal log animation
        const logs = [
            "> [TRINITY] Rebalancing Funding Arb...",
            "> [HFT] Alpha filled LONG 0.5 BTC @ MKT",
            "> [SYS] Latency spike detected... routed to backup node.",
            "> [ORACLE] Sentiment shift detected on SOL",
            "> [WHALE] Suspicious activity on On-chain wallets...",
            "> [MEV] Arbitrage opportunity found! Executing Flashloan...",
            "> [MEV] Flashloan success. Profit: 0.04 ETH",
            "> [HFT] Delta scaling out of INJ position."
        ];
        const logContainer = document.getElementById('log-container');
        
        setInterval(() => {
            if (Math.random() > 0.3) {
                const newLog = logs[Math.floor(Math.random() * logs.length)];
                logContainer.innerHTML += newLog + "<br>";
                if (logContainer.childElementCount > 15) {
                    logContainer.innerHTML = logContainer.innerHTML.substring(logContainer.innerHTML.indexOf("<br>") + 4);
                }
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
