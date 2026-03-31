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
            overflow-x: hidden;
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
            animation: flicker 3s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1);
            pointer-events: none;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-warning { color: yellow; text-shadow: 0 0 5px yellow; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border-bottom: 1px dashed #333; padding: 5px; text-align: left; }
        th { color: var(--neon-blue); }
        
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        @keyframes flicker {
            0% { opacity: 1; }
            5% { opacity: 0.8; }
            10% { opacity: 1; }
            15% { opacity: 0.4; }
            20% { opacity: 1; }
            100% { opacity: 1; }
        }
        
        .trinity-panel { border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); color: var(--neon-pink); }
        .trinity-panel h2 { text-shadow: 0 0 5px var(--neon-pink); }
        .trinity-panel th { color: var(--neon-pink); }
        .trinity-panel .status-online { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA TACTICAL DASHBOARD 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPTIME: 99.9% | LATENCY: 12ms</p>
        <p style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr>
                    <th>Unità</th>
                    <th>Strategia</th>
                    <th>Stato</th>
                </tr>
                <tr>
                    <td>🦅 SQUADRA_ALPHA</td>
                    <td>Scalper [Binance]</td>
                    <td class="status-active blink">ENGAGING</td>
                </tr>
                <tr>
                    <td>🦈 SQUADRA_DELTA</td>
                    <td>Order Flow</td>
                    <td class="status-active blink">HUNTING</td>
                </tr>
                <tr>
                    <td>🐍 SQUADRA_GAMMA</td>
                    <td>Pairs Trading [Bitget]</td>
                    <td class="status-online">STANDBY</td>
                </tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p>Background Daemons operativi e sincronizzati.</p>
            <table>
                <tr>
                    <th>Agente</th>
                    <th>Ruolo</th>
                    <th>Stato</th>
                </tr>
                <tr>
                    <td>🕴️ Lo Strozzino</td>
                    <td>Funding Arb</td>
                    <td class="status-online blink">ACTIVE</td>
                </tr>
                <tr>
                    <td>🧮 Il Contabile</td>
                    <td>DCA Accumulation</td>
                    <td class="status-online blink">ACTIVE</td>
                </tr>
                <tr>
                    <td>👼 L'Angelo Custode</td>
                    <td>MEV [Arbitrum]</td>
                    <td class="status-online blink">MONITORING</td>
                </tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>Sensore</th>
                    <th>Dato Corrente</th>
                    <th>Trend</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance)</td>
                    <td>Bullish Bias 68%</td>
                    <td class="status-online">▲</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>Inflow: +4.2K BTC</td>
                    <td class="status-warning">~</td>
                </tr>
                <tr>
                    <td>⚡ Volatility Index</td>
                    <td>Elevata (VIX crypto)</td>
                    <td class="status-active">▲</td>
                </tr>
            </table>
        </div>
        
        <!-- TERMINAL LOG -->
        <div class="panel" style="grid-column: 1 / -1; border-color: #555;">
            <h2>>_ TACTICAL FEED</h2>
            <div style="height: 120px; overflow: hidden; color: #888; font-size: 0.9em; line-height: 1.5;">
                <p>> [SYS] Initiating Orbital Scan...</p>
                <p>> [ALPHA] Executed long order #88492 at optimal liquidity node.</p>
                <p>> [ANGELO] Block #1938472 analyzed. No MEV opportunities detected. Resuming scan.</p>
                <p>> [STROZZINO] Funding rate skew detected on Bybit. Rebalancing hedged positions.</p>
                <p class="blink" style="color: yellow; text-shadow: 0 0 5px yellow;">> [WARNING] High volatility detected in sector 4. Adjusting risk parameters automatically.</p>
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
    # Default Flask port 5000, modify if needed.
    app.run(host='0.0.0.0', port=5000, debug=False)
