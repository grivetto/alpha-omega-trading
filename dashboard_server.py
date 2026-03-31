from flask import Flask, render_template_string
import os

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
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 10, 0.8);
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
            text-shadow: 0 0 10px var(--neon-green);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }
        .header h1 { color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); }
        
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px var(--neon-green) inset;
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: 0 0 20px var(--neon-green) inset, 0 0 10px var(--neon-green);
        }
        .panel.trinity {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 10px var(--neon-pink) inset;
        }
        .panel.trinity:hover {
            box-shadow: 0 0 20px var(--neon-pink) inset, 0 0 10px var(--neon-pink);
        }
        .panel.trinity h2 { text-shadow: 0 0 10px var(--neon-pink); }
        
        .panel.metrics {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue) inset;
        }
        .panel.metrics:hover {
            box-shadow: 0 0 20px var(--neon-blue) inset, 0 0 10px var(--neon-blue);
        }
        .panel.metrics h2 { text-shadow: 0 0 10px var(--neon-blue); }

        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; padding: 5px; border-left: 2px solid; }
        .assault li { border-color: var(--neon-green); }
        .trinity li { border-color: var(--neon-pink); }
        
        .status {
            float: right;
            animation: blink 1s infinite;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status.active { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); animation: blink 0.5s infinite; }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(0, 255, 255, 0.4); }
            70% { box-shadow: 0 0 20px 10px rgba(0, 255, 255, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 255, 255, 0); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 5s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid var(--neon-blue); padding: 8px; text-align: left; }
        th { background-color: rgba(0, 255, 255, 0.1); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p>QUANTITATIVE TACTICAL DASHBOARD // SYSTEM ONLINE</p>
        <div style="margin-top: 15px; color: var(--neon-pink); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 10px var(--neon-pink); border: 1px solid var(--neon-pink); padding: 10px; display: inline-block; border-radius: 5px; background: rgba(255, 0, 255, 0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel assault">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺 
                    <span class="status active">[ENGAGING]</span>
                    <br><small>Scalper su Binance | Latency: 12ms</small>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅 
                    <span class="status online">[STANDBY]</span>
                    <br><small>Order Flow Analysis | Depth Scanning</small>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐍 
                    <span class="status online">[ONLINE]</span>
                    <br><small>Pairs Trading su Bitget | Hedge Active</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>LO STROZZINO</strong> 🏦 
                    <span class="status online">[YIELDING]</span>
                    <br><small>Funding Arb | Harvesting Rates</small>
                </li>
                <li>
                    <strong>IL CONTABILE</strong> 🧮 
                    <span class="status online">[ACCUMULATING]</span>
                    <br><small>Smart DCA | Matrix execution</small>
                </li>
                <li>
                    <strong>L'ANGELO CUSTODE</strong> 🛡️ 
                    <span class="status active">[PROTECTING]</span>
                    <br><small>MEV Arbitrum | Frontrun Shield</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>Modulo</th>
                    <th>Stato / Valore</th>
                </tr>
                <tr>
                    <td>👁️ THE ORACLE (Binance Sentiment)</td>
                    <td id="oracle-val" style="color: var(--neon-green); font-weight:bold;">BULLISH (78%)</td>
                </tr>
                <tr>
                    <td>🐋 WHALE TRACKER</td>
                    <td style="color: var(--neon-red); font-weight:bold;">LARGE INFLOW ALERTS</td>
                </tr>
                <tr>
                    <td>⚡ NETWORK CONGESTION</td>
                    <td>LOW (15 Gwei)</td>
                </tr>
                <tr>
                    <td>⏱️ GLOBAL UPTIME</td>
                    <td>99.999%</td>
                </tr>
            </table>
        </div>
    </div>
    <script>
        // Fake dynamic updates for Oracle
        setInterval(() => {
            const oracles = ["BULLISH (78%)", "BULLISH (81%)", "NEUTRAL (55%)", "BEARISH (42%)", "STRONG BUY (90%)"];
            document.getElementById("oracle-val").innerText = oracles[Math.floor(Math.random() * oracles.length)];
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Flask app runner
    app.run(host='0.0.0.0', port=5000)
