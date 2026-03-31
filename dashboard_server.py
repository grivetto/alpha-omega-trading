from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image:
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 10px rgba(57, 255, 20, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid transparent;
            background: linear-gradient(45deg, var(--neon-green), var(--neon-blue)) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
            opacity: 0.5;
        }
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.2em;
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px;
            background: rgba(0, 255, 0, 0.05);
            border-left: 3px solid var(--neon-green);
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: pulse 2s infinite;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .metric-box {
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid var(--neon-blue);
            padding: 15px 10px;
            text-align: center;
            border-radius: 3px;
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.1);
        }
        .metric-value {
            font-size: 1.5em;
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            margin: 8px 0;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            left: 0;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 6s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ NUVOLA // ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>SQUADRA_ALPHA <br><span style="font-size: 0.8em; color: #888;">(Binance Scalper)</span></span>
                <span class="status-online">[ ONLINE ] 🟢</span>
            </div>
            <div class="status">
                <span>SQUADRA_DELTA <br><span style="font-size: 0.8em; color: #888;">(Order Flow)</span></span>
                <span class="status-online">[ ONLINE ] 🟢</span>
            </div>
            <div class="status">
                <span>SQUADRA_GAMMA <br><span style="font-size: 0.8em; color: #888;">(Bitget Pairs)</span></span>
                <span class="status-online">[ ONLINE ] 🟢</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status">
                <span>Lo Strozzino <br><span style="font-size: 0.8em; color: #888;">(Funding Arb)</span></span>
                <span class="status-online">ACTIVE 🟢</span>
            </div>
            <div class="status">
                <span>Il Contabile <br><span style="font-size: 0.8em; color: #888;">(DCA)</span></span>
                <span class="status-online">ACTIVE 🟢</span>
            </div>
            <div class="status">
                <span>L'Angelo Custode <br><span style="font-size: 0.8em; color: #888;">(MEV Arbitrum)</span></span>
                <span class="status-online">ACTIVE 🟢</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #ccc;">The Oracle (Binance)</div>
                    <div class="metric-value">BULLISH 🟢</div>
                    <div style="font-size: 0.8em; color: var(--neon-green);">Score: 84/100</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #ccc;">Whale Tracker</div>
                    <div class="metric-value">INFLOW 🐋</div>
                    <div style="font-size: 0.8em; color: var(--neon-pink);">+4,250 BTC</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #ccc;">Liquidations (1H)</div>
                    <div class="metric-value" style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">$14.2M</div>
                    <div style="font-size: 0.8em; color: var(--neon-pink);">Shorts REKT</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: #ccc;">Network Latency</div>
                    <div class="metric-value" style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">12ms</div>
                    <div style="font-size: 0.8em; color: var(--neon-green);">Optimal</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
