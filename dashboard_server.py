from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff073a;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-cyan);
            color: var(--neon-cyan);
            animation: flicker 2s infinite alternate;
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15);
            border-radius: 8px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.1);
            pointer-events: none;
        }
        h2 {
            color: var(--neon-magenta);
            border-bottom: 2px solid var(--neon-magenta);
            padding-bottom: 5px;
            text-shadow: 0 0 8px var(--neon-magenta);
            margin-top: 0;
        }
        ul { list-style-type: none; padding: 0; }
        li { margin: 15px 0; font-size: 1.2em; display: flex; justify-content: space-between;}
        .status-online {
            color: var(--neon-green);
            animation: pulse 1.5s infinite;
            text-shadow: 0 0 8px var(--neon-green);
        }
        .status-alert {
            color: var(--neon-red);
            animation: fast-pulse 0.5s infinite;
            text-shadow: 0 0 8px var(--neon-red);
        }
        @keyframes pulse {
            0% { opacity: 1; text-shadow: 0 0 10px var(--neon-green); }
            50% { opacity: 0.6; text-shadow: none; }
            100% { opacity: 1; text-shadow: 0 0 10px var(--neon-green); }
        }
        @keyframes fast-pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.8; }
        }
        .blink { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.5em; color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green);" class="blink">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    <div class="grid">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 <b>SQUADRA_ALPHA</b> (Binance Scalp)</span> <span class="status-online">[ENGAGED]</span></li>
                <li><span>🌊 <b>SQUADRA_DELTA</b> (Order Flow)</span> <span class="status-online">[MONITORING]</span></li>
                <li><span>⚖️ <b>SQUADRA_GAMMA</b> (Bitget Pairs)</span> <span class="status-online">[ACTIVE]</span></li>
            </ul>
        </div>
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🩸 <b>Lo Strozzino</b> (Funding Arb)</span> <span class="status-online">[BACKGROUND SECURE]</span></li>
                <li><span>🧮 <b>Il Contabile</b> (DCA)</span> <span class="status-online">[ACCUMULATING]</span></li>
                <li><span>👼 <b>L'Angelo Custode</b> (MEV Arb)</span> <span class="status-online">[GUARDING]</span></li>
            </ul>
        </div>
        <div class="panel" style="grid-column: 1 / span 2;">
            <h2>📊 METRICHE DI MERCATO (LIVE FEED)</h2>
            <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 20px;">
                <div>
                    <h3 style="color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">👁️ THE ORACLE (Sentiment)</h3>
                    <p class="blink" style="font-size: 2.5em; margin: 10px 0;">EXTREME GREED <br/> [ 88 ]</p>
                </div>
                <div>
                    <h3 style="color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">🐋 WHALE TRACKER</h3>
                    <p style="font-size: 1.5em; margin: 10px 0;">DETECTED: 5,000 BTC ➔ COINBASE</p>
                    <p class="status-alert" style="font-size: 1.5em; margin: 0;">! ALERT LEVEL: HIGH !</p>
                </div>
                <div>
                    <h3 style="color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">⚡ PING (BINANCE API)</h3>
                    <p class="status-online" style="font-size: 2.5em; margin: 10px 0;">14 ms</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    # Run securely on the local network/localhost by default, or 0.0.0.0 to expose
    app.run(host='0.0.0.0', port=5000)
