from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola Dashboard</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: #111;
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
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            margin-bottom: 20px;
            font-weight: bold;
        }
        .header-title {
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            font-size: 2.5em;
            letter-spacing: 4px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 10px rgba(57, 255, 20, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.trinity {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.2), inset 0 0 10px rgba(255, 0, 255, 0.1);
        }
        .panel.trinity::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.trinity h2 { text-shadow: 0 0 10px var(--neon-pink); }
        
        .panel.intel {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
        }
        .panel.intel::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.intel h2 { text-shadow: 0 0 10px var(--neon-blue); }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1.5s infinite alternate;
            margin-right: 5px;
        }
        .status-indicator.pink { background-color: var(--neon-pink); box-shadow: 0 0 8px var(--neon-pink); }
        
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 5px;
        }
        .glitch {
            animation: glitch 3s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>
    <h1 class="header-title glitch">🛰️ ORBITAL COMMAND 🛰️</h1>
    <h3 style="color: #888; text-shadow: none;">Nuvola Quantitative Dashboard v3.0</h3>
    <div style="text-align: center; margin: 20px 0; padding: 10px; background: rgba(255,0,255,0.1); border: 1px solid var(--neon-pink); color: var(--neon-pink); font-size: 1.2em; text-shadow: 0 0 5px var(--neon-pink);">
        <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span><span class="status-indicator"></span> SQUADRA_ALPHA (Binance Scalp)</span>
                <span>[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span> SQUADRA_DELTA (Order Flow)</span>
                <span>[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator"></span> SQUADRA_GAMMA (Bitget Pairs)</span>
                <span>[ ENGAGED ]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #aaa;">
                > Win Rate (24h): 76.4% <br>
                > Latency: 12ms
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span><span class="status-indicator pink"></span> Lo Strozzino (Funding Arb)</span>
                <span>[ ACTIVE ]</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator pink"></span> Il Contabile (DCA)</span>
                <span>[ ACTIVE ]</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator pink"></span> L'Angelo Custode (MEV Arb)</span>
                <span>[ ACTIVE ]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #aaa;">
                > Capital Deployed: 100% <br>
                > System Integrity: Nominal
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel intel">
            <h2>👁️ METRICHE & INTEL</h2>
            <div class="data-row">
                <span>🔮 The Oracle (Sentiment)</span>
                <span style="color: #39ff14;">BULLISH 78%</span>
            </div>
            <div class="data-row">
                <span>🐋 Whale Tracker</span>
                <span style="color: #ffaa00; font-weight: bold; animation: blink 1s infinite alternate;">ALERT: 50k ETH Moved</span>
            </div>
            <div class="data-row">
                <span>🌐 Global Liquidity</span>
                <span>STABLE</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #aaa;">
                > Last Update: SYNCED <br>
                > Ping: 8ms
            </div>
        </div>
    </div>
    
    <div style="margin-top: 40px; text-align: center; color: #444; font-size: 0.8em; text-shadow: none;">
        SYSTEM SECURE. UNAUTHORIZED ACCESS WILL BE TERMINATED.
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Binding to all interfaces so it can be accessed
    app.run(host='0.0.0.0', port=5000, debug=False)
