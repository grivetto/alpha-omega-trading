import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-purple: #bc13fe;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-green);
            font-size: 2.5em;
            margin-bottom: 30px;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        .panel h2 {
            color: var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 10px;
            margin-top: 0;
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
        }
        .status-warning {
            color: #ffaa00;
            text-shadow: 0 0 5px #ffaa00;
        }
        .status-purple {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #333;
            padding: 5px 0;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .terminal {
            margin-top: 20px;
            background: #000;
            border: 1px solid var(--neon-green);
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.8em;
            box-shadow: inset 0 0 10px var(--neon-green);
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; font-weight: bold; color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); animation: blink 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[SQUADRA_ALPHA]</strong> ⚡ Scalper (Binance)<br>
                    <span class="status-online">● STATUS: ENGAGED [APRs: 142%]</span>
                </li>
                <li>
                    <strong>[SQUADRA_DELTA]</strong> 🌊 Order Flow<br>
                    <span class="status-online">● STATUS: MONITORING TAPE</span>
                </li>
                <li>
                    <strong>[SQUADRA_GAMMA]</strong> ⚖️ Pairs Trading (Bitget)<br>
                    <span class="status-online">● STATUS: HEDGED [Spread: 0.15%]</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🕵️‍♂️ LO STROZZINO</strong> (Funding Arb)<br>
                    <span class="status-purple">▶ BACKGROUND HARVESTING ACTIVE</span>
                </li>
                <li>
                    <strong>🧮 IL CONTABILE</strong> (DCA)<br>
                    <span class="status-purple">▶ SCHEDULED BUY IN 04:22:10</span>
                </li>
                <li>
                    <strong>👼 L'ANGELO CUSTODE</strong> (MEV Arbitrum)<br>
                    <span class="status-purple">▶ MEMPOOL SNIPING ONLINE</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span>🔮 THE ORACLE (Sentiment)</span>
                <span class="status-online">EXTREME GREED (82)</span>
            </div>
            <div class="data-row">
                <span>🐳 WHALE TRACKER</span>
                <span class="status-warning">LARGE OUTFLOW DETECTED</span>
            </div>
            <div class="data-row">
                <span>🌐 NETWORK CONGESTION</span>
                <span>14 GWEI</span>
            </div>
            <div class="data-row">
                <span>LIQUIDATION HEATMAP</span>
                <span class="status-online">CALIBRATED</span>
            </div>
        </div>
    </div>

    <div class="terminal">
        <div id="log"></div>
    </div>

    <script>
        const logs = [
            "> SYSTEM INIT...",
            "> CONNECTING TO BINANCE WEBSOCKET...",
            "> ESTABLISHING BITGET API SECURE LINK...",
            "> SQUADRA_ALPHA: EXECUTING BUY 0.15 BTC @ $94,200",
            "> THE ORACLE: DETECTED TWITTER SPIKE FOR $DOGE",
            "> ANGELO CUSTODE: FRONT-RUN OPPORTUNITY IDENTIFIED ON ARBITRUM",
            "> LO STROZZINO: COLLECTING FUNDING FEES (+0.01% / 8h)",
            "> SYSTEM OPTIMAL. ALL SYSTEMS NOMINAL."
        ];
        const logEl = document.getElementById('log');
        let i = 0;
        setInterval(() => {
            if (i < logs.length) {
                logEl.innerHTML += logs[i] + "<br>";
                i++;
            } else {
                logEl.innerHTML = "";
                i = 0;
            }
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start the server on port 5000 (adjust as needed)
    app.run(host='0.0.0.0', port=5000, debug=False)
