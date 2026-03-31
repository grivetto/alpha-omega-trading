from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-color: #00ffcc;
            --accent-glow: #00ffcc;
            --danger-glow: #ff003c;
            --warning-glow: #ffcc00;
            --panel-bg: rgba(0, 20, 40, 0.6);
            --border-color: #005577;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 204, 0.05) 25%, rgba(0, 255, 204, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, 0.05) 75%, rgba(0, 255, 204, 0.05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 204, 0.05) 25%, rgba(0, 255, 204, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, 0.05) 75%, rgba(0, 255, 204, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--accent-glow);
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--accent-glow);
            padding-bottom: 10px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 255, 204, 0.2);
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 85, 119, 0.5);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--accent-glow);
            box-shadow: 0 0 10px var(--accent-glow);
        }
        .status-online {
            color: #00ff00;
            text-shadow: 0 0 8px #00ff00;
        }
        .status-offline {
            color: var(--danger-glow);
            text-shadow: 0 0 8px var(--danger-glow);
        }
        .status-standby {
            color: var(--warning-glow);
            text-shadow: 0 0 8px var(--warning-glow);
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,204,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            border-bottom: 1px dashed var(--border-color);
            padding-bottom: 5px;
        }
        .data-value {
            float: right;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND | NUVOLA</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPLINK: SECURE | ENCRYPTION: AES-256</p>
        <div style="margin-top: 15px; font-size: 1.2em; font-weight: bold; color: var(--warning-glow); text-shadow: 0 0 10px var(--warning-glow);">
            ⚙️ PROTOCOLLO TRINITY: <span class="status-online blink">Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong> (Scalper su Binance)<br>
                    Status: <span class="status-online">ENGAGED</span>
                    <span class="data-value">+1.24% PnL</span>
                </li>
                <li>
                    <strong>⚡ SQUADRA_DELTA</strong> (Order Flow)<br>
                    Status: <span class="status-standby">STANDBY - MONITORING</span>
                    <span class="data-value">0.00% PnL</span>
                </li>
                <li>
                    <strong>⚖️ SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)<br>
                    Status: <span class="status-online">ENGAGED</span>
                    <span class="data-value">+0.89% PnL</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🦈 Lo Strozzino</strong> (Funding Arb)<br>
                    Status: <span class="status-online blink">ACTIVE</span>
                    <span class="data-value">APR 18.4%</span>
                </li>
                <li>
                    <strong>💼 Il Contabile</strong> (DCA)<br>
                    Status: <span class="status-online">ACTIVE</span>
                    <span class="data-value">Accumulo BTC/ETH</span>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Status: <span class="status-online blink">HUNTING</span>
                    <span class="data-value">0 tx frontrunned</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong>🔮 The Oracle</strong> (Binance Sentiment)<br>
                    Fear & Greed: <span class="status-standby">72 (GREED)</span>
                </li>
                <li>
                    <strong>🐳 Whale Tracker</strong><br>
                    Large Tx (>100 BTC): <span class="status-offline">DETECTED (3 mins ago)</span>
                </li>
                <li>
                    <strong>📊 Volatility Index</strong><br>
                    VIX (Crypto): <span class="status-online">LOW (45.2)</span>
                </li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
