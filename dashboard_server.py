import os
import time
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        :root {
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --border-color: #00ffcc;
            --text-main: #e0f7fa;
            --text-glow: #00ffcc;
            --alert-color: #ff0055;
            --success-color: #00ffaa;
            --font-main: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 204, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 204, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 10px var(--text-glow);
            margin-top: 0;
        }

        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--border-color);
            box-shadow: 0 5px 15px rgba(0, 255, 204, 0.2);
            margin-bottom: 30px;
            animation: pulse 4s infinite alternate;
        }

        @keyframes pulse {
            0% { box-shadow: 0 5px 15px rgba(0, 255, 204, 0.1); }
            100% { box-shadow: 0 5px 25px rgba(0, 255, 204, 0.4); }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 10px rgba(0, 255, 204, 0.1), 0 0 10px rgba(0, 255, 204, 0.2);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 15px rgba(0, 255, 204, 0.3), 0 0 20px rgba(0, 255, 204, 0.4);
            transform: translateY(-2px);
        }

        .panel-title {
            border-bottom: 1px solid rgba(0, 255, 204, 0.5);
            padding-bottom: 10px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .status {
            font-size: 0.8em;
            padding: 3px 8px;
            border-radius: 3px;
            animation: blink 2s infinite;
        }

        .status.online { background: rgba(0, 255, 170, 0.2); color: var(--success-color); border: 1px solid var(--success-color); }
        .status.active { background: rgba(0, 255, 204, 0.2); color: var(--text-glow); border: 1px solid var(--border-color); }
        .status.alert { background: rgba(255, 0, 85, 0.2); color: var(--alert-color); border: 1px solid var(--alert-color); }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 10px; font-size: 0.9em; display: flex; justify-content: space-between; }
        .value { color: var(--text-glow); font-weight: bold; }
        .metric-row { display: flex; justify-content: space-between; margin-bottom: 5px; }

        .scan-line {
            width: 100%;
            height: 2px;
            background: rgba(0, 255, 204, 0.5);
            position: fixed;
            top: 0;
            left: 0;
            z-index: 9999;
            animation: scan 6s linear infinite;
            pointer-events: none;
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
        <h1>🛰️ NUVOLA | ORBITAL COMMAND</h1>
        <p>Tactical Quantitative Dashboard v2.0</p>
        <div style="margin-top: 15px; color: var(--success-color); font-weight: bold; border: 1px solid var(--success-color); display: inline-block; padding: 8px 15px; border-radius: 4px; background: rgba(0, 255, 170, 0.1); box-shadow: 0 0 10px rgba(0, 255, 170, 0.2);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-title">
                <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            </div>
            <ul>
                <li>
                    <span>⚡ SQUADRA_ALPHA (Binance Scalper)</span>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                    <span class="status active">ENGAGED</span>
                </li>
                <li>
                    <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                    <span class="status active">ENGAGED</span>
                </li>
            </ul>
            <div style="margin-top: 15px; border-top: 1px dashed rgba(0,255,204,0.3); padding-top: 10px;">
                <div class="metric-row"><span>Alpha Win Rate:</span> <span class="value">68.4%</span></div>
                <div class="metric-row"><span>Delta Flow Delta:</span> <span class="value">+1.2M USDT</span></div>
                <div class="metric-row"><span>Gamma Spread:</span> <span class="value">0.15%</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-title">
                <h2>🔺 PROTOCOLLO TRINITY</h2>
            </div>
            <ul>
                <li>
                    <span>🕴️ Lo Strozzino (Funding Arb)</span>
                    <span class="status online">ONLINE</span>
                </li>
                <li>
                    <span>🧮 Il Contabile (DCA)</span>
                    <span class="status online">ONLINE</span>
                </li>
                <li>
                    <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                    <span class="status online">ONLINE</span>
                </li>
            </ul>
            <div style="margin-top: 15px; border-top: 1px dashed rgba(0,255,204,0.3); padding-top: 10px;">
                <div class="metric-row"><span>Arb Yield (APR):</span> <span class="value">14.2%</span></div>
                <div class="metric-row"><span>DCA Progress:</span> <span class="value">75%</span></div>
                <div class="metric-row"><span>MEV Captured:</span> <span class="value">0.45 ETH</span></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-title">
                <h2>📊 METRICHE DI MERCATO</h2>
            </div>
            <ul>
                <li>
                    <span>👁️ The Oracle (Binance Sentiment)</span>
                    <span class="status active">ANALYZING</span>
                </li>
                <li>
                    <span>🐋 Whale Tracker</span>
                    <span class="status alert">ALERT</span>
                </li>
            </ul>
            <div style="margin-top: 15px; border-top: 1px dashed rgba(0,255,204,0.3); padding-top: 10px;">
                <div class="metric-row"><span>BTC Sentiment:</span> <span class="value" style="color:var(--success-color)">BULLISH (72)</span></div>
                <div class="metric-row"><span>Whale Flow (24h):</span> <span class="value" style="color:var(--alert-color)">-5,400 BTC</span></div>
                <div class="metric-row"><span>Market Volatility:</span> <span class="value">HIGH</span></div>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; font-size: 0.8em; opacity: 0.7;">
        <p>SYS.REQ.OK // ENCRYPTION: AES-256 // LINK: SECURE</p>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
