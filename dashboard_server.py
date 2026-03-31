from flask import Flask, render_template_string
import threading
import time
import random

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
            --neon-cyan: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-yellow: #fffb00;
            --neon-red: #ff073a;
            --panel-bg: rgba(10, 15, 30, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 243, 255, 0.05) 25%, rgba(0, 243, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, 0.05) 75%, rgba(0, 243, 255, 0.05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 243, 255, 0.05) 25%, rgba(0, 243, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, 0.05) 75%, rgba(0, 243, 255, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-cyan);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 4s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2), inset 0 0 10px rgba(0, 243, 255, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan));
            animation: scanline 3s linear infinite;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-active { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .status-warning { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-left: 2px solid var(--neon-cyan); padding-left: 10px; }
        
        .metric-box {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(0,243,255,0.3);
            padding: 5px 0;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-cyan); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }
        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; }
            100% { opacity: 0.7; }
        }
        .blink { animation: pulse 1.5s infinite; }
    </style>
</head>
<body>
    <div class="header">
        <h1 style="font-size: 2.5em; letter-spacing: 5px;">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p class="blink" style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">[ SYSTEM ONLINE // ENCRYPTED CONNECTION ]</p>
        <p style="color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-red); border-bottom: 1px solid var(--neon-red);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[ SQUADRA_ALPHA ]</strong> <span class="status-online">ENGAGED</span><br>
                    <small>Target: Binance Scalping | Latency: 12ms | ROI/h: +0.4%</small>
                </li>
                <li>
                    <strong>[ SQUADRA_DELTA ]</strong> <span class="status-active">MONITORING</span><br>
                    <small>Target: Order Flow Analysis | Imbalance: LONG</small>
                </li>
                <li>
                    <strong>[ SQUADRA_GAMMA ]</strong> <span class="status-online">ENGAGED</span><br>
                    <small>Target: Bitget Pairs Trading | Spread: 0.15% | PnL: +$142</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); border-bottom: 1px solid var(--neon-pink);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> <span class="status-online">BACKGROUND</span><br>
                    <small>Mission: Funding Arb | Current APR: 18.5% | Exposure: Hedged</small>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> <span class="status-online">BACKGROUND</span><br>
                    <small>Mission: Smart DCA | Next Buy: BTC @ $61,200 | Accumulation: Active</small>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> <span class="status-online">BACKGROUND</span><br>
                    <small>Mission: MEV Arbitrum | Frontruns: 0 | Gas saved: 4.2 ETH</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-yellow); border-bottom: 1px solid var(--neon-yellow);">📊 METRICHE DI MERCATO</h2>
            <div class="metric-box">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span class="status-active blink">EXTREME GREED (82)</span>
            </div>
            <div class="metric-box">
                <span>🐋 Whale Tracker (Large TXs)</span>
                <span class="status-warning">MASSIVE INFLOW ($450M)</span>
            </div>
            <div class="metric-box">
                <span>📈 BTC Dominance</span>
                <span class="status-online">54.2%</span>
            </div>
            <div class="metric-box">
                <span>🌐 Global Hashrate</span>
                <span class="status-online">640 EH/s</span>
            </div>
            <br>
            <div style="text-align: center; font-size: 0.8em; color: gray;">
                [ DATA STREAMING REAL-TIME... ]
            </div>
        </div>
    </div>
    
    <script>
        // Fake real-time updates for effect
        setInterval(() => {
            const elements = document.querySelectorAll('.metric-box span:nth-child(2)');
            // Randomly toggle slightly to simulate live data
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on standard 5050 for testing, change as needed
    app.run(host='0.0.0.0', port=5050)
