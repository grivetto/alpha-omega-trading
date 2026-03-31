import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --text-main: #e0e0e0;
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background: rgba(10, 10, 10, 0.8);
            border: 1px solid #333;
            padding: 15px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
        }
        .panel-hft::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel-hft h2 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        
        .panel-trinity::before { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        .panel-trinity h2 { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        
        .panel-market::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel-market h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }

        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 5px;
            border-bottom: 1px dashed #333;
        }
        .online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
        }
        .active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .standby { color: #aaa; }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            background: #111;
            padding: 10px;
            border: 1px solid #222;
            text-align: center;
        }
        .metric-value {
            font-size: 1.5em;
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .scan-line {
            width: 100%;
            height: 2px;
            background: rgba(0, 255, 255, 0.1);
            position: fixed;
            top: 0;
            left: 0;
            animation: scan 5s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        @keyframes scan {
            0% { top: 0; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM ONLINE // TERMINAL SECURE // QUANTITATIVE MILITARY DASHBOARD</p>
    </div>

    <div class="container">
        <!-- STATO GLOBALE TRINITY -->
        <div class="panel panel-trinity" style="grid-column: span 2; text-align: center; background: rgba(0,255,0,0.1);">
            <h2 style="margin: 0;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h2>
        </div>

        <!-- SQUADRE D'ASSALTO -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="active">[ ENGAGED ]</span>
            </div>
            <div class="status">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="online">[ MONITORING ]</span>
            </div>
            <div class="status">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="active">[ ARBITRAGE ]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>💠 PROTOCOLLO TRINITY</h2>
            <div class="status">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-market" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO / THE ORACLE</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>BINANCE SENTIMENT INDEX</div>
                    <div class="metric-value">GREED (78)</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER (24H VOLUME)</div>
                    <div class="metric-value">$1.24B</div>
                </div>
                <div class="metric-box">
                    <div>ARBITRUM MEV OPPORTUNITIES</div>
                    <div class="metric-value">DETECTED (3)</div>
                </div>
                <div class="metric-box">
                    <div>GLOBAL SYSTEM STATUS</div>
                    <div class="metric-value" style="color:var(--neon-green); text-shadow:0 0 5px var(--neon-green);">NOMINAL</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
