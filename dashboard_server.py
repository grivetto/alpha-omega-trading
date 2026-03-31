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
            --bg: #050505;
            --text: #0f0;
            --accent: #00ffcc;
            --danger: #ff003c;
            --warn: #ffea00;
            --panel-bg: rgba(0, 255, 170, 0.05);
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            color: var(--accent);
            text-shadow: 0 0 10px var(--accent);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--accent);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--accent);
            box-shadow: 0 0 15px rgba(0, 255, 170, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .status {
            float: right;
            animation: pulse 1.5s infinite;
        }
        .status.online { color: var(--text); }
        .status.active { color: var(--accent); }
        .status.warning { color: var(--warn); }
        
        @keyframes pulse {
            0% { opacity: 1; text-shadow: 0 0 5px currentColor; }
            50% { opacity: 0.5; text-shadow: none; }
            100% { opacity: 1; text-shadow: 0 0 5px currentColor; }
        }
        
        .log-box {
            height: 150px;
            overflow-y: auto;
            background: rgba(0,0,0,0.8);
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.9em;
            color: #aaa;
            margin-top: 15px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed #333;
            margin-bottom: 10px;
            padding-bottom: 5px;
        }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #333; padding: 5px; text-align: left; }
        th { color: var(--accent); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA // ORBITAL COMMAND</h1>
        <p>SYSTEM STATUS: <span class="status online">ONLINE</span> | UPLINK: SECURE | TACTICAL OVERVIEW</p>
        <div style="margin-top: 10px; padding: 10px; background: var(--panel-bg); border: 1px solid var(--accent); display: inline-block; font-weight: bold; box-shadow: 0 0 10px rgba(0,255,170,0.3);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status active">[ENGAGING]</span>
            </div>
            <div class="metric">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="status active">[SCANNING]</span>
            </div>
            <div class="metric">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status online">[STANDBY]</span>
            </div>
            <div class="log-box">
                > ALPHA: Executed buy BTC/USDT @ 64,210.5<br>
                > DELTA: Massive volume spike detected on ETH perp<br>
                > GAMMA: Spread narrowing, holding fire.<br>
                > ALPHA: Target reached, taking profit.
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🩸 LO STROZZINO (Funding Arb)</span>
                <span class="status online">[BACKGROUND]</span>
            </div>
            <div class="metric">
                <span>🧮 IL CONTABILE (DCA)</span>
                <span class="status online">[BACKGROUND]</span>
            </div>
            <div class="metric">
                <span>🛡️ L'ANGELO CUSTODE (MEV Arbitrum)</span>
                <span class="status active">[PATROLLING]</span>
            </div>
            <p style="color: var(--warn); font-size: 0.8em; margin-top: 15px;" class="blink">WARNING: High gas fees on L1. MEV ops isolated to L2.</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 MARKET INTEL</h2>
            <div class="metric">
                <span>👁️ THE ORACLE (Binance Sentiment)</span>
                <span class="status warning">EXTREME GREED</span>
            </div>
            <div class="metric">
                <span>🐋 WHALE TRACKER</span>
                <span class="status active">DETECTED 5k BTC MOVE</span>
            </div>
            <table>
                <tr><th>Asset</th><th>Action</th><th>Confidence</th></tr>
                <tr><td>BTC</td><td>LONG</td><td>87%</td></tr>
                <tr><td>ETH</td><td>HOLD</td><td>54%</td></tr>
                <tr><td>SOL</td><td>SHORT</td><td>92%</td></tr>
            </table>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; color: #555; font-size: 0.8em;">
        &copy; 2026 QUANTITATIVE WARFARE DIVISION // NUVOLA
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
