from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌐</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(0, 255, 0, 0.05);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-cyan);
            color: var(--neon-cyan);
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            border: 1px solid var(--neon-green);
            background: var(--panel-bg);
            padding: 15px;
            box-shadow: 0 0 10px var(--neon-green) inset;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 15px var(--neon-green);
            pointer-events: none;
            z-index: -1;
            animation: pulse 2s infinite alternate;
        }
        @keyframes pulse {
            from { opacity: 0.5; }
            to { opacity: 1; }
        }
        .status-online {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            animation: blink 1.5s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        ul { list-style-type: none; padding: 0; }
        li { margin: 15px 0; border-bottom: 1px dashed #333; padding-bottom: 10px; }
        .metric { display: flex; justify-content: space-between; }
        .pink-glow { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2>NUVOLA TACTICAL DASHBOARD</h2>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px dashed var(--neon-pink); padding: 10px; color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <div class="panel">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            <ul>
                <li>🐺 <b>SQUADRA_ALPHA</b> <br><small>(Scalper Binance)</small> <br><span class="status-online">[ONLINE - DEPLOYED]</span></li>
                <li>🎯 <b>SQUADRA_DELTA</b> <br><small>(Order Flow)</small> <br><span class="status-online">[ONLINE - SCANNING]</span></li>
                <li>⚖️ <b>SQUADRA_GAMMA</b> <br><small>(Pairs Trading Bitget)</small> <br><span class="status-online">[ONLINE - ARB ACTIVE]</span></li>
            </ul>
        </div>

        <div class="panel">
            <h3>🛡️ PROTOCOLLO TRINITY</h3>
            <ul>
                <li>🕴️ <b>Lo Strozzino</b> <br><small>(Funding Arb)</small> <br><span class="status-online">[ONLINE - YIELDING]</span></li>
                <li>🧮 <b>Il Contabile</b> <br><small>(DCA)</small> <br><span class="status-online">[ONLINE - ACCUMULATING]</span></li>
                <li>👼 <b>L'Angelo Custode</b> <br><small>(MEV Arbitrum)</small> <br><span class="status-online">[ONLINE - PROTECTING]</span></li>
            </ul>
        </div>

        <div class="panel">
            <h3>📊 METRICHE DI MERCATO</h3>
            <ul>
                <li class="metric"><span>👁️ THE ORACLE (Sentiment):</span> <span class="pink-glow">EXTREME GREED (88)</span></li>
                <li class="metric"><span>🐋 WHALE TRACKER:</span> <span class="pink-glow">LARGE INFLOWS DETECTED</span></li>
                <li class="metric"><span>⚡ VOLATILITY INDEX:</span> <span class="status-online">HIGH (VIX 24.5)</span></li>
                <li class="metric"><span>🌐 SYSTEM UPTIME:</span> <span>99.99%</span></li>
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
    app.run(host='0.0.0.0', port=8080)