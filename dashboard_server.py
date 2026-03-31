from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-shadow: 0 0 5px var(--neon-green);
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            border-bottom: 1px solid;
            padding-bottom: 5px;
        }
        h1 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); text-align: center; }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.1);
            pointer-events: none;
        }
        .status-online {
            color: var(--neon-green);
            animation: blink 2s infinite;
        }
        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .status-standby {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .scanline {
            width: 100%;
            height: 2px;
            background: rgba(57, 255, 20, 0.3);
            position: absolute;
            top: 0;
            left: 0;
            animation: scan 5s linear infinite;
            pointer-events: none;
        }
        @keyframes scan {
            0% { top: 0; }
            100% { top: 100%; }
        }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-left: 2px solid var(--neon-green); padding-left: 10px; }
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            border: 1px dashed var(--neon-blue);
            padding: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND TERMINAL</h1>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); border-color: var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    <span style="font-size: 0.9em;">[Binance Scalper]</span><br>
                    Status: <span class="status-active">ENGAGED</span> | PNL: <span class="status-online">+2.4%</span>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    <span style="font-size: 0.9em;">[Order Flow]</span><br>
                    Status: <span class="status-online">MONITORING</span> | Volatility: High
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐍<br>
                    <span style="font-size: 0.9em;">[Bitget Pairs Trading]</span><br>
                    Status: <span class="status-active">ARBITRAGE ACTIVE</span> | Spread: 0.15%
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); border-color: var(--neon-blue);">🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 10px; padding: 5px; border: 1px dashed var(--neon-green); text-align: center;" class="status-online">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🕴️<br>
                    <span style="font-size: 0.9em;">[Funding Arb]</span><br>
                    Status: <span class="status-online">BACKGROUND ONLINE</span> | Yield: 14% APY
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮<br>
                    <span style="font-size: 0.9em;">[DCA Engine]</span><br>
                    Status: <span class="status-online">BACKGROUND ONLINE</span> | Next Buy: 4h 12m
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 👼<br>
                    <span style="font-size: 0.9em;">[MEV Arbitrum]</span><br>
                    Status: <span class="status-standby">DEFENSE MODE</span> | Blocks Scanned: 1.2M
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <strong>The Oracle</strong> 👁️<br>
                    <span style="font-size: 0.8em;">Binance Sentiment</span><br>
                    <span style="color: var(--neon-green); font-size: 1.2em;">BULLISH (78%)</span>
                </div>
                <div class="metric-box">
                    <strong>Whale Tracker</strong> 🐋<br>
                    <span style="font-size: 0.8em;">Large TXNs</span><br>
                    <span style="color: var(--neon-pink); font-size: 1.2em;">INFLOW: 4.2K BTC</span>
                </div>
                <div class="metric-box">
                    <strong>Global Liq</strong> 💧<br>
                    <span style="font-size: 0.8em;">Aggregated</span><br>
                    <span class="status-online">STABLE</span>
                </div>
                <div class="metric-box">
                    <strong>System Load</strong> ⚙️<br>
                    <span style="font-size: 0.8em;">Nuvola Core</span><br>
                    <span class="status-active">14% CPU</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
