import os
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
            --neon-cyan: #0ff;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            letter-spacing: 5px;
            text-transform: uppercase;
            margin-bottom: 40px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.15);
            padding: 20px;
            border-radius: 4px;
            position: relative;
        }
        .panel h2 {
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            padding: 12px;
            background: rgba(57, 255, 20, 0.03);
            border-left: 3px solid var(--neon-green);
            font-weight: bold;
        }
        .status.active { border-color: var(--neon-green); }
        .status.warning { border-color: var(--neon-cyan); color: var(--neon-cyan); }
        .status.danger { border-color: var(--neon-red); color: var(--neon-red); }
        
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #222; padding: 10px; text-align: left; }
        th { color: var(--neon-cyan); font-weight: bold; border-bottom: 2px solid var(--neon-cyan); }
        td { color: #ccc; }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.85em;
            color: #444;
            letter-spacing: 2px;
        }
    </style>
</head>
<body>
    <h1><span class="blink">🔴</span> ORBITAL COMMAND <span class="blink">🔴</span></h1>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active pulse">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span>[ ONLINE ]</span>
            </div>
            <div class="status warning">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span>[ STANDBY ]</span>
            </div>
            <div class="status active">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span>[ ENGAGED ]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; color: var(--neon-cyan); font-weight: bold; font-size: 1.1em; border: 1px dashed var(--neon-cyan); padding: 10px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status active">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span style="color:var(--neon-green)">[ HARVESTING ]</span>
            </div>
            <div class="status active">
                <span>🧮 Il Contabile (DCA)</span>
                <span style="color:var(--neon-green)">[ ACCUMULATING ]</span>
            </div>
            <div class="status danger blink">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span>[ SNIPING ]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <table>
                <tr><th>Source</th><th>Metric</th><th>Value</th></tr>
                <tr><td>👁️ The Oracle</td><td>Binance Sentiment</td><td style="color:var(--neon-cyan); font-weight:bold;">BULLISH 78%</td></tr>
                <tr><td>🐋 Whale Tracker</td><td>Large Inflow</td><td style="color:var(--neon-red); font-weight:bold;">+4,500 BTC</td></tr>
                <tr><td>📉 Liquidity</td><td>OB Imbalance</td><td>-1.2%</td></tr>
                <tr><td>🌐 Network</td><td>Gas (Gwei)</td><td>12.5</td></tr>
            </table>
        </div>
    </div>
    
    <div class="footer">
        SYSTEM NOMINAL. CONNECTION SECURE. NUVOLA QUANTITATIVE ENGINE V3.1
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue il server
    app.run(host='0.0.0.0', port=5000, debug=False)
