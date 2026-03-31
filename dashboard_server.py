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
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 15, 10, 0.8);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.2);
        }
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: inset 0 0 10px var(--neon-green);
            pointer-events: none;
        }
        .pink-panel {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
        }
        .pink-panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink), 0 0 10px var(--neon-pink);
        }
        .pink-panel::before { box-shadow: inset 0 0 10px var(--neon-pink); }
        
        .blue-panel {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
        }
        .blue-panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue);
        }
        .blue-panel::before { box-shadow: inset 0 0 10px var(--neon-blue); }

        .status-online { color: #0f0; text-shadow: 0 0 5px #0f0; }
        .status-standby { color: #ff0; text-shadow: 0 0 5px #ff0; }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); animation: blink 1s infinite; }

        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }
        
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(57, 255, 20, 0.3);
            opacity: 0.6;
            animation: scanline 6s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-bottom: 1px dashed rgba(255,255,255,0.2); padding-bottom: 5px; }
        
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            border: 1px solid rgba(0, 255, 255, 0.5);
            padding: 10px;
            text-align: center;
            background: rgba(0, 255, 255, 0.05);
        }
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND CENTCOM 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPLINK: SECURE | NUVOLA CORE ACTIVATED</p>
        <p style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🦅<br>
                    <small>Binance Scalper [Aggressive]</small><br>
                    Status: <span class="status-active">ENGAGED</span> | PnL: +$142.50
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🎯<br>
                    <small>Order Flow Dynamics</small><br>
                    Status: <span class="status-online">MONITORING</span> | Targets: 3
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> ⚖️<br>
                    <small>Bitget Pairs Trading</small><br>
                    Status: <span class="status-standby">BALANCING</span> | Spread: 0.4%
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel pink-panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🏦<br>
                    <small>Funding Rate Arb [Background]</small><br>
                    Status: <span class="status-online">GATHERING YIELD</span>
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮<br>
                    <small>DCA Engine & Rebalancer</small><br>
                    Status: <span class="status-online">CALCULATING</span>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 🛡️<br>
                    <small>MEV Protection Arbitrum</small><br>
                    Status: <span class="status-active">SHIELD ACTIVE</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel blue-panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>THE ORACLE 🔮</div>
                    <div class="metric-value status-active" id="oracle-status">BULLISH</div>
                    <small>Binance Sentiment</small>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER 🐋</div>
                    <div class="metric-value status-online">INFLOW</div>
                    <small>+$45M 24h</small>
                </div>
                <div class="metric-box">
                    <div>VOLATILITY INDEX ⚡</div>
                    <div class="metric-value status-standby">MED</div>
                    <small>VIX-Crypto</small>
                </div>
                <div class="metric-box">
                    <div>GLOBAL LIQUIDITY 💧</div>
                    <div class="metric-value status-online">STABLE</div>
                    <small>M2 Monitor</small>
                </div>
            </div>
            <br>
            <div style="text-align: center; border: 1px dashed var(--neon-blue); padding: 5px;">
                <small>DATA FEEDS: SYNCHRONIZED</small>
            </div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const oracles = ['BULLISH', 'BEARISH', 'NEUTRAL', 'HYPER-BULL'];
            const colors = ['#ff00ff', '#f00', '#ff0', '#39ff14'];
            const idx = Math.floor(Math.random() * 4);
            const oracleEl = document.getElementById('oracle-status');
            oracleEl.innerText = oracles[idx];
            oracleEl.style.color = colors[idx];
            oracleEl.style.textShadow = `0 0 5px ${colors[idx]}`;
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start the server on port 5000 (adjust if another port is usually expected)
    app.run(host='0.0.0.0', port=5000)
