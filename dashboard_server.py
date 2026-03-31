import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-purple: #bc13fe;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 30, 0.8);
            --grid-color: rgba(0, 255, 255, 0.1);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px rgba(0, 255, 255, 0.1);
            animation: pulse 2s infinite;
        }
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.2), 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-standby {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }
        .status-alert {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .metric-box {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed var(--neon-green);
            padding: 5px 0;
        }
        .metric-box:last-child { border-bottom: none; }
        
        @keyframes pulse {
            0% { box-shadow: 0 10px 20px rgba(0, 255, 255, 0.1); }
            50% { box-shadow: 0 10px 20px rgba(0, 255, 255, 0.3); }
            100% { box-shadow: 0 10px 20px rgba(0, 255, 255, 0.1); }
        }
        @keyframes scanline {
            0% { transform: translateY(0); }
            100% { transform: translateY(100%); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        .blink { animation: blink 1s infinite; }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPLINK: SECURE | LOCATION: NUVOLA</p>
        <p style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); font-weight: bold; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric-box">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status-online">[ENGAGED]</span>
            </div>
            <div class="metric-box">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">[ACTIVE]</span>
            </div>
            <div class="metric-box">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-standby">[STANDBY]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Target acquisition in progress...<br>
                > Latency: 12ms
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">👁️ PROTOCOLLO TRINITY</h2>
            <div class="metric-box">
                <span>🧛 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">SYPHONING</span>
            </div>
            <div class="metric-box">
                <span>🧮 Il Contabile (Smart DCA)</span>
                <span class="status-online">ACCUMULATING</span>
            </div>
            <div class="metric-box">
                <span>🛡️ L'Angelo Custode (Arbitrum MEV)</span>
                <span class="status-online">GUARDING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Trinity synchronization stable.<br>
                > Background daemons nominal.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">📊 METRICHE DI MERCATO</h2>
            <div class="metric-box">
                <span>🔮 The Oracle (Sentiment)</span>
                <span>FEAR [32] <span class="status-alert">⚠️</span></span>
            </div>
            <div class="metric-box">
                <span>🐋 Whale Tracker</span>
                <span>LARGE MOVES DETECTED</span>
            </div>
            <div class="metric-box">
                <span>💸 Global Liquidity Index</span>
                <span class="status-online">OPTIMAL</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Awaiting next oracle pulse...<br>
                > Market volatility index: HIGH
            </div>
        </div>
    </div>

    <div style="margin-top: 30px; text-align: center; color: var(--neon-blue); opacity: 0.5;">
        <p>TERMINAL v4.2.0 // UNAUTHORIZED ACCESS WILL BE LETHAL</p>
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
