import os
from flask import Flask, render_template_string

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
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-green: #39ff14;
            --dark-bg: #0a0a0c;
            --panel-bg: #111116;
        }
        body {
            background-color: var(--dark-bg);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-magenta);
            padding-bottom: 10px;
            animation: flicker 2s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            padding: 20px;
            border-radius: 5px;
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: 0 0 15px var(--neon-cyan);
            border-color: var(--neon-magenta);
        }
        .panel h2 {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 10px;
            font-size: 1.2em;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin: 15px 0;
            border-left: 2px solid var(--neon-cyan);
            padding-left: 10px;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
                text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan);
            }
            20%, 24%, 55% {
                text-shadow: none;
            }
        }
        .metric { display: flex; justify-content: space-between; border-bottom: 1px solid #333; padding: 8px 0;}
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND | NUVOLA TERMINAL</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid var(--neon-magenta); padding: 10px; background: rgba(255, 0, 255, 0.1); border-radius: 5px;">
        <span class="status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>SQUADRA_ALPHA</strong> 🐺<br> <small>Scalper | Binance</small> <span class="status-online">[ ACTIVE ]</span></li>
                <li><strong>SQUADRA_DELTA</strong> 🦅<br> <small>Order Flow Analytics</small> <span class="status-online">[ ACTIVE ]</span></li>
                <li><strong>SQUADRA_GAMMA</strong> 🐍<br> <small>Pairs Trading | Bitget</small> <span class="status-online">[ ACTIVE ]</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>⚕️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>LO STROZZINO</strong> 🏦<br> <small>Funding Arb</small> <span class="status-online">[ ONLINE BACKGROUND ]</span></li>
                <li><strong>IL CONTABILE</strong> 🧮<br> <small>DCA Strategy</small> <span class="status-online">[ ONLINE BACKGROUND ]</span></li>
                <li><strong>L'ANGELO CUSTODE</strong> 👼<br> <small>MEV | Arbitrum</small> <span class="status-online">[ ONLINE BACKGROUND ]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric"><span>THE ORACLE (Sentiment)</span> <span style="color:var(--neon-magenta)">BULLISH [78%]</span></div>
            <div class="metric"><span>WHALE TRACKER</span> <span style="color:var(--neon-cyan)">INFLOW +$42.5M</span></div>
            <div class="metric"><span>VOLATILITY INDEX</span> <span style="color:var(--neon-green)">MODERATE</span></div>
            <div class="metric"><span>SYS. LATENCY</span> <span>12ms</span></div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
