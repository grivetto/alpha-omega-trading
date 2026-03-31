import os
import time
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
            --bg-color: #050505;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-purple: #b026ff;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
            --font-mono: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-mono);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }
        .header h1 { margin: 0; font-size: 2.5em; }
        .header p { color: var(--neon-purple); margin-top: 5px; font-weight: bold; }
        
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .panel {
            background: rgba(10, 10, 10, 0.8);
            border: 1px solid #333;
            border-radius: 5px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
            border-color: var(--neon-blue);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }
        
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .panel h2 {
            margin-top: 0;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            border-bottom: 1px dotted #444;
            padding-bottom: 10px;
            font-size: 1.2em;
        }
        
        /* Tactical list items */
        .item {
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-blue);
        }
        .item-title { font-weight: bold; color: var(--neon-blue); }
        .item-status { float: right; color: var(--neon-green); animation: blink 2s infinite; }
        .item-desc { font-size: 0.9em; color: #888; margin-top: 5px; }
        
        /* Trinity Protocol Section */
        .trinity .item-title { color: var(--neon-purple); }
        .trinity .item { border-left-color: var(--neon-purple); }
        
        /* Market Metrics */
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }
        .metric-box {
            background: #111;
            padding: 10px;
            text-align: center;
            border: 1px solid #222;
        }
        .metric-value { font-size: 1.5em; color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .metric-label { font-size: 0.8em; color: #666; text-transform: uppercase; }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .sys-log {
            margin-top: 30px;
            padding: 15px;
            background: #000;
            border: 1px solid #333;
            height: 150px;
            overflow-y: auto;
            font-size: 0.85em;
            color: #555;
            font-family: var(--font-mono);
        }
        .log-line { margin: 4px 0; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND</h1>
        <p>/// NUVOLA TACTICAL DASHBOARD v3.0 ///</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(0,255,0,0.1); color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); display: inline-block; border-radius: 5px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span class="item-title">SQUADRA_ALPHA</span>
                <span class="item-status">[ ENGAGED ]</span>
                <div class="item-desc">Scalper // Target: Binance // Ping: 12ms</div>
            </div>
            <div class="item">
                <span class="item-title">SQUADRA_DELTA</span>
                <span class="item-status">[ ACTIVE ]</span>
                <div class="item-desc">Order Flow Analysis // Heatmap Tracking</div>
            </div>
            <div class="item">
                <span class="item-title">SQUADRA_GAMMA</span>
                <span class="item-status">[ STANDBY ]</span>
                <div class="item-desc">Pairs Trading // Target: Bitget // Spread monitoring</div>
            </div>
        </div>

        <!-- TRINITY PROTOCOL -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="item">
                <span class="item-title">LO STROZZINO</span>
                <span class="item-status">[ ONLINE ]</span>
                <div class="item-desc">Funding Arb Engine // Harvesting Yields</div>
            </div>
            <div class="item">
                <span class="item-title">IL CONTABILE</span>
                <span class="item-status">[ ONLINE ]</span>
                <div class="item-desc">DCA Accumulator // Stealth Mode</div>
            </div>
            <div class="item">
                <span class="item-title">L'ANGELO CUSTODE</span>
                <span class="item-status">[ ONLINE ]</span>
                <div class="item-desc">MEV Protection // Network: Arbitrum</div>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="item-desc">Connected to: The Oracle & Whale Tracker</div>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-value">68.4%</div>
                    <div class="metric-label">Binance Sentiment</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">0.89</div>
                    <div class="metric-label">Long/Short Ratio</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">🚨 ALERT</div>
                    <div class="metric-label">Whale Movement</div>
                </div>
                <div class="metric-box">
                    <div class="metric-value">14.2Gwei</div>
                    <div class="metric-label">Arb Gas Fees</div>
                </div>
            </div>
            
            <div class="sys-log">
                <div class="log-line"><span class="log-time">05:21:00</span> [SYS] Dashboard UI re-initialized.</div>
                <div class="log-line"><span class="log-time">05:21:02</span> [ORACLE] Processing sentiment stream...</div>
                <div class="log-line"><span class="log-time">05:21:05</span> [ALPHA] Order filled on BTC/USDT.</div>
                <div class="log-line"><span class="log-time">05:21:08</span> [STROZZINO] Rebalancing funding rates.</div>
                <div class="log-line"><span class="log-time">05:21:10</span> [WHALE] Large transfer detected: 5000 ETH.</div>
            </div>
        </div>
    </div>
    <script>
        // Simple script to update log times dynamically and make the log auto-scroll
        setInterval(() => {
            const logs = document.querySelector('.sys-log');
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0];
            const messages = [
                "[ALPHA] Scanning orderbook...",
                "[DELTA] Updating liquidity heatmap...",
                "[GAMMA] Spread variance nominal.",
                "[SYS] Pinging Arbitrum RPC...",
                "[ORACLE] Sentiment shifting neutral.",
                "[CONTABILE] Executing DCA batch...",
                "[CUSTODE] Mempool scanned. Clear."
            ];
            const msg = messages[Math.floor(Math.random() * messages.length)];
            
            const div = document.createElement('div');
            div.className = 'log-line';
            div.innerHTML = `<span class="log-time">${timeStr}</span> ${msg}`;
            
            logs.appendChild(div);
            logs.scrollTop = logs.scrollHeight;
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on default flask port or custom
    app.run(host='0.0.0.0', port=5000, debug=False)
