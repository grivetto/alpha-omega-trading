from flask import Flask, render_template_string
import random
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
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-magenta: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, .05) 25%, rgba(0, 255, 0, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, .05) 75%, rgba(0, 255, 0, .05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 0, .05) 25%, rgba(0, 255, 0, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, .05) 75%, rgba(0, 255, 0, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            margin-bottom: 10px;
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            animation: flicker 3s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2);
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(0,255,0,0.1), transparent);
            animation: scan 4s linear infinite;
        }
        .status-online {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            animation: pulse 1.5s infinite;
        }
        .status-active {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-warning {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
        }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 15px; border-bottom: 1px dashed rgba(0,255,0,0.3); padding-bottom: 5px; }
        .glitch { position: relative; }
        .data-row { display: flex; justify-content: space-between; font-size: 0.9em; margin-top: 5px; }
        
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 24%, 55% { opacity: 0.5; text-shadow: none; }
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        @keyframes scan {
            0% { left: -100%; }
            100% { left: 200%; }
        }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND : NUVOLA 🛰️</h1>
    
    <div style="text-align: center; font-size: 1.2em; margin-bottom: 20px; padding: 10px; border: 1px solid var(--neon-blue); background-color: rgba(0, 255, 255, 0.1); color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); font-weight: bold; animation: pulse 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    <span class="data-row"><span>Target: Binance Scalper</span> <span class="status-active">[ ENGAGED ]</span></span>
                    <span class="data-row"><span>Latency:</span> <span>12ms</span></span>
                    <span class="data-row"><span>Win Rate:</span> <span>68.4%</span></span>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    <span class="data-row"><span>Target: Order Flow</span> <span class="status-active">[ ENGAGED ]</span></span>
                    <span class="data-row"><span>Imbalance:</span> <span class="status-warning">Long 62%</span></span>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐍<br>
                    <span class="data-row"><span>Target: Bitget Pairs</span> <span class="status-active">[ ENGAGED ]</span></span>
                    <span class="data-row"><span>Spread Arb:</span> <span>0.15%</span></span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🕴️<br>
                    <span class="data-row"><span>Role: Funding Arb</span> <span class="status-online">[ ONLINE ]</span></span>
                    <span class="data-row"><span>Yield (24h):</span> <span>+0.045%</span></span>
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮<br>
                    <span class="data-row"><span>Role: Smart DCA</span> <span class="status-online">[ ONLINE ]</span></span>
                    <span class="data-row"><span>Next Buy:</span> <span>04:00:00</span></span>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 🛡️<br>
                    <span class="data-row"><span>Role: MEV Arbitrum</span> <span class="status-online">[ ONLINE ]</span></span>
                    <span class="data-row"><span>Blocks Scanned:</span> <span>14,502</span></span>
                    <span class="data-row"><span>Tx Rescued:</span> <span>2</span></span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong>The Oracle</strong> 👁️<br>
                    <span class="data-row"><span>Binance Sentiment:</span> <span class="status-warning">EXTREME GREED (82)</span></span>
                    <span class="data-row"><span>Vol Index:</span> <span>High</span></span>
                </li>
                <li>
                    <strong>Whale Tracker</strong> 🐋<br>
                    <span class="data-row"><span>Large Tx (1h):</span> <span>24 detected</span></span>
                    <span class="data-row"><span>Net Flow:</span> <span class="status-warning">-4,500 BTC</span></span>
                    <span class="data-row"><span>Target Alert:</span> <span class="status-online">Wallet 0x7a... active</span></span>
                </li>
                <li>
                    <strong>System Status</strong> ⚙️<br>
                    <span class="data-row"><span>Memory:</span> <span>42%</span></span>
                    <span class="data-row"><span>CPU:</span> <span>18%</span></span>
                    <span class="data-row"><span>Uptime:</span> <span>99.99%</span></span>
                </li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
