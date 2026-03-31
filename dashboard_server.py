import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌌</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        h1, h2, h3 {
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 3px;
            text-shadow: 0 0 8px var(--neon-cyan), 0 0 15px var(--neon-cyan);
            color: var(--neon-cyan);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.3), inset 0 0 15px rgba(0, 255, 255, 0.1);
            padding: 20px;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-cyan);
            box-shadow: 0 0 15px var(--neon-cyan);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            0% { top: 0; opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            animation: pulse 2s infinite;
        }
        .status-offline {
            color: red;
            text-shadow: 0 0 8px red;
        }
        .status-warning {
            color: #ffaa00;
            text-shadow: 0 0 8px #ffaa00;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }
        .squad { margin-bottom: 20px; border-bottom: 1px dashed rgba(0,255,255,0.3); padding-bottom: 15px; }
        .squad:last-child { border-bottom: none; }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .metric-box {
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid var(--neon-magenta);
            padding: 15px;
            text-align: center;
            box-shadow: 0 0 8px rgba(255, 0, 255, 0.4);
            transition: all 0.3s ease;
        }
        .metric-box:hover {
            transform: scale(1.05);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.7);
        }
        .metric-value { font-size: 1.8em; font-weight: bold; color: var(--neon-magenta); text-shadow: 0 0 8px var(--neon-magenta); margin-top: 10px; }
    </style>
</head>
<body>
    <h1>🛰️ Orbital Command - Nuvola</h1>
    <h3 class="status-online">● SYS_CORE ONLINE - SECURE CONNECTION ENCRYPTED</h3>
    <h3 class="status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="squad">
                <strong>🐺 SQUADRA_ALPHA</strong> (Scalper su Binance)<br>
                Status: <span class="status-online">ACTIVE</span> | Posizioni: 3 | PnL: <span class="status-online">+1.24%</span>
            </div>
            <div class="squad">
                <strong>⚡ SQUADRA_DELTA</strong> (Order Flow)<br>
                Status: <span class="status-online">ACTIVE</span> | Flusso: Alto | PnL: <span class="status-online">+0.89%</span>
            </div>
            <div class="squad">
                <strong>⚖️ SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)<br>
                Status: <span class="status-online">ACTIVE</span> | Spread: 0.05% | PnL: <span class="status-online">+0.42%</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="squad">
                <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                Status: <span class="status-online">BACKGROUND</span> | Target: Bybit/Binance
            </div>
            <div class="squad">
                <strong>🧮 Il Contabile</strong> (DCA)<br>
                Status: <span class="status-online">BACKGROUND</span> | Allocazione: 65% Deploy
            </div>
            <div class="squad">
                <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                Status: <span class="status-online">MONITORING MEMPOOL</span> | Frontrun: Pronto
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>🔮 The Oracle (Sentiment)</div>
                    <div class="metric-value status-online">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>🐋 Whale Tracker</div>
                    <div class="metric-value status-warning">ACCUMULO</div>
                </div>
                <div class="metric-box">
                    <div>🔥 BTC Volatility</div>
                    <div class="metric-value">ALTA (4.2%)</div>
                </div>
                <div class="metric-box">
                    <div>💧 Liquidity Pool</div>
                    <div class="metric-value status-online">STABILE</div>
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
    app.run(host='0.0.0.0', port=5000, debug=False)
