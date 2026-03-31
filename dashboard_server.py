import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --bg-dark: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 2.5em;
            margin: 0;
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue);
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: inset 0 0 10px #000, 0 0 10px var(--neon-green);
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(57, 255, 20, 0.2), transparent);
            transform: skewX(-20deg);
            animation: scan 3s infinite linear;
        }
        @keyframes scan {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .status-online { color: var(--neon-green); font-weight: bold; animation: blink 1.5s infinite; }
        .status-active { color: var(--neon-blue); font-weight: bold; }
        .status-standby { color: var(--neon-pink); font-weight: bold; }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        ul { list-style-type: none; padding: 0; }
        li { margin: 8px 0; border-bottom: 1px dashed #333; padding-bottom: 5px; }
        .value { float: right; }
        .glow-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .glow-pink { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 NUVOLA ORBITAL COMMAND 🌐</h1>
        <p>QUANTITATIVE MILITARY DASHBOARD // SYS_STATUS: <span class="status-online">ONLINE</span></p>
        <p style="font-weight: bold; color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>⚡ <strong>SQUADRA_ALPHA</strong> (Binance Scalper) <span class="value status-active">[ ENGAGED ]</span></li>
                <li>🌊 <strong>SQUADRA_DELTA</strong> (Order Flow) <span class="value status-active">[ MONITORING ]</span></li>
                <li>⚖️ <strong>SQUADRA_GAMMA</strong> (Bitget Pairs) <span class="value status-active">[ ARBITRAGE ]</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-blue">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>🕴️ <strong>Lo Strozzino</strong> (Funding Arb) <span class="value glow-blue">[ ONLINE ]</span></li>
                <li>🧮 <strong>Il Contabile</strong> (DCA) <span class="value glow-blue">[ ONLINE ]</span></li>
                <li>👼 <strong>L'Angelo Custode</strong> (MEV Arb) <span class="value glow-blue">[ ONLINE ]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="glow-pink">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>👁️ <strong>The Oracle</strong> (Binance Sentiment) <span class="value glow-pink">BULLISH 68%</span></li>
                <li>🐋 <strong>Whale Tracker</strong> (Large Tx) <span class="value glow-pink">DETECTED: 12</span></li>
                <li>📈 <strong>Global Volatility</strong> (VIX) <span class="value glow-pink">ELEVATED</span></li>
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
