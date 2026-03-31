from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-pink: #ff007f;
            --neon-blue: #00f3ff;
            --bg-color: #050505;
            --panel-bg: #0a0a0a;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
        }
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 5px;
        }
        .status {
            float: right;
            animation: blink 2s infinite;
        }
        .status.online { color: var(--neon-blue); }
        .status.active { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-bottom: 1px solid #111; padding-bottom: 5px; }
        .metric { color: white; float: right; }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND DASHBOARD 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); border: 1px solid var(--neon-green); padding: 10px; border-radius: 5px; background: rgba(57, 255, 20, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>🐺 SQUADRA_ALPHA <br><small>Scalper Binance</small> <span class="status active">[ ENGAGED ]</span></li>
                <li>⚡ SQUADRA_DELTA <br><small>Order Flow</small> <span class="status active">[ ENGAGED ]</span></li>
                <li>⚖️ SQUADRA_GAMMA <br><small>Pairs Trading Bitget</small> <span class="status active">[ ENGAGED ]</span></li>
            </ul>
        </div>
        
        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>🦇 LO STROZZINO <br><small>Funding Arb</small> <span class="status online">[ ONLINE ]</span></li>
                <li>🧮 IL CONTABILE <br><small>DCA Strategy</small> <span class="status online">[ ONLINE ]</span></li>
                <li>👼 L'ANGELO CUSTODE <br><small>MEV Arbitrum</small> <span class="status online">[ ONLINE ]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>🔮 THE ORACLE (Sentiment) <span class="metric" style="color:var(--neon-green)">BULLISH 78%</span></li>
                <li>🐋 WHALE TRACKER <span class="metric" style="color:var(--neon-pink)">ALERT: $50M INFLOW</span></li>
                <li>📈 VOLATILITY INDEX <span class="metric" style="color:var(--neon-blue)">ELEVATED</span></li>
                <li>⏱️ SYSTEM LATENCY <span class="metric">12ms</span></li>
            </ul>
        </div>
    </div>
    <div style="text-align:center; margin-top:30px; color:#555; font-size:12px;">
        SECURE CONNECTION ESTABLISHED // ALL SYSTEMS NOMINAL // NUVOLA NETWORK
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
