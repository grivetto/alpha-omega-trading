from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola Dashboard</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff073a;
            --neon-purple: #bc13fe;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
            --border-glow: 0 0 10px;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 4s infinite alternate;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: var(--border-glow) var(--neon-green);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(57, 255, 20, 0.1), transparent);
            animation: scanline 3s infinite linear;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            font-weight: bold;
        }
        .status-standby {
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            font-weight: bold;
        }
        .status-active {
            color: var(--neon-red);
            text-shadow: 0 0 8px var(--neon-red);
            font-weight: bold;
            animation: pulse 1s infinite;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 8px;
            border-bottom: 1px dotted rgba(57, 255, 20, 0.3);
            padding-bottom: 4px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            text-align: center;
        }
        .metric-box {
            border: 1px solid var(--neon-blue);
            padding: 10px;
            color: var(--neon-blue);
            box-shadow: 0 0 5px var(--neon-blue);
        }
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            margin-top: 5px;
        }
        @keyframes scanline {
            100% { left: 200%; }
        }
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; }
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .terminal-output {
            font-size: 0.9em;
            color: #ccc;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <h3>SYSTEM: NUVOLA QUANTITATIVE ENGINE | STATUS: <span class="status-online">NOMINAL</span></h3>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺 [Binance Scalper]<br>
                    Status: <span class="status-active">ENGAGED</span> | PnL (24h): +4.2% | Latency: 12ms
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅 [Order Flow]<br>
                    Status: <span class="status-online">MONITORING</span> | Order Imbalance: Bullish 68%
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐍 [Bitget Pairs Trading]<br>
                    Status: <span class="status-active">ARBITRAGE EXECUTING</span> | Target Spread: 0.85%
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="background-color: rgba(57, 255, 20, 0.1); padding: 10px; border: 1px solid var(--neon-green); margin-bottom: 10px; font-weight: bold; text-align: center;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <p class="terminal-output">> Initializing background daemon structures...</p>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🕴️ [Funding Arb]<br>
                    Status: <span class="status-standby">ONLINE BACKGROUND</span> | Capturing Yield: 24.5% APR
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮 [DCA Accumulation]<br>
                    Status: <span class="status-standby">ONLINE BACKGROUND</span> | Next Buy: 4h 12m
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 🛡️ [MEV Arbitrum]<br>
                    Status: <span class="status-standby">ONLINE BACKGROUND</span> | Frontruns averted: 14
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO (RADAR INTEL)</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>🔮 The Oracle (Binance Sentiment)</div>
                    <div class="metric-value" style="color: var(--neon-green)">EXTREME GREED</div>
                </div>
                <div class="metric-box">
                    <div>🐋 Whale Tracker</div>
                    <div class="metric-value status-active">LARGE INFLOW DETECTED</div>
                </div>
                <div class="metric-box">
                    <div>⚡ Global Volatility Index</div>
                    <div class="metric-value">High (42.1)</div>
                </div>
            </div>
            <p class="terminal-output" style="margin-top: 15px;">
                > [SYS] Fetching live mempool data... OK<br>
                > [SYS] Re-calibrating neural net weights... OK<br>
                > [SYS] Orbital Command standing by for manual override.
            </p>
        </div>

    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000 or from env
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
