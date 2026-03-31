from flask import Flask, render_template_string

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
            --bg: #050505;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff3333;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            animation: flicker 2s infinite;
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
            20%, 24%, 55% { text-shadow: none; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.2em;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-standby {
            color: var(--neon-blue);
            font-weight: bold;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            border-bottom: 1px solid #111;
        }
        .blink {
            animation: blinker 1s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);" class="blink">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>🔴 SQUADRA_ALPHA (Binance Scalp)</span>
                <span class="status-online blink">[ ENGAGED ]</span>
            </div>
            <div class="metric">
                <span>🔵 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">[ ACTIVE ]</span>
            </div>
            <div class="metric">
                <span>🟣 SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-standby">[ STANDBY ]</span>
            </div>
            <br>
            <div style="font-size: 0.8em; color: #888;">> Executing high-frequency tactical maneuvers...</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🦈 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ YIELDING ]</span>
            </div>
            <div class="metric">
                <span>🧮 Il Contabile (DCA Grid)</span>
                <span class="status-online">[ ACCUMULATING ]</span>
            </div>
            <div class="metric">
                <span>👼 L'Angelo Custode (MEV Arb)</span>
                <span class="status-online blink">[ SNIPING ]</span>
            </div>
            <br>
            <div style="font-size: 0.8em; color: #888;">> Background wealth generation routines nominal...</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 THE ORACLE & METRICS</h2>
            <div class="metric">
                <span>👁️ Binance Sentiment Index</span>
                <span style="color: var(--neon-blue);">78 (GREED)</span>
            </div>
            <div class="metric">
                <span>🐋 Whale Tracker Alert</span>
                <span style="color: var(--neon-red);" class="blink">WARNING: 50k BTC MOVED</span>
            </div>
            <div class="metric">
                <span>⚡ Network Latency</span>
                <span>12ms</span>
            </div>
            <br>
            <div style="font-size: 0.8em; color: #888;">> Real-time neural sentiment extraction...</div>
        </div>
    </div>
    
    <div style="margin-top: 30px; text-align: center; font-size: 0.8em; opacity: 0.7;">
        SYSTEM STATUS: <span class="status-online">NOMINAL</span> | UPTIME: 99.99% | SECURE CONNECTION
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
