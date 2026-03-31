from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola: Orbital Command</title>
    <style>
        :root {
            --bg-color: #050505;
            --grid-color: rgba(0, 255, 255, 0.1);
            --text-main: #00ffcc;
            --text-alert: #ff0055;
            --text-warn: #ffcc00;
            --border-neon: 0 0 10px #00ffcc, inset 0 0 10px #00ffcc;
            --border-alert: 0 0 10px #ff0055, inset 0 0 10px #ff0055;
        }
        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            text-shadow: 0 0 15px var(--text-main);
            font-size: 2.5em;
            margin-bottom: 30px;
            letter-spacing: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            border: 1px solid var(--text-main);
            box-shadow: var(--border-neon);
            padding: 15px;
            background: rgba(0, 20, 20, 0.8);
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -50%; left: -50%; width: 200%; height: 200%;
            background: linear-gradient(transparent, rgba(0, 255, 204, 0.1), transparent);
            transform: rotate(45deg);
            animation: scan 4s linear infinite;
        }
        @keyframes scan {
            0% { top: -100%; }
            100% { top: 100%; }
        }
        h2 {
            border-bottom: 1px dashed var(--text-main);
            padding-bottom: 5px;
            font-size: 1.2em;
            margin-top: 0;
        }
        .status-ok { color: var(--text-main); text-shadow: 0 0 5px var(--text-main); }
        .status-warn { color: var(--text-warn); text-shadow: 0 0 5px var(--text-warn); }
        .status-alert { color: var(--text-alert); text-shadow: 0 0 5px var(--text-alert); }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; font-size: 0.9em; display: flex; justify-content: space-between; align-items: center; }
        .blink { animation: blink 1s step-end infinite; }
        @keyframes blink { 50% { opacity: 0; } }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.8em; }
        th, td { border: 1px solid var(--text-main); padding: 5px; text-align: left; }
        th { background: rgba(0, 255, 204, 0.2); }
    </style>
</head>
<body>
    <h1>🛰️ Nuvola Orbital Command 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; font-weight: bold; color: var(--text-warn); text-shadow: 0 0 10px var(--text-warn);" class="blink">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🦅 SQUADRA_ALPHA (Binance Scalper)</span> <span class="status-ok blink">[ENGAGED]</span></li>
                <li><span>🎯 SQUADRA_DELTA (Order Flow)</span> <span class="status-warn">[STANDBY]</span></li>
                <li><span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span> <span class="status-ok blink">[ENGAGED]</span></li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--text-warn);">
                > Alpha PnL (24h): +4.2%<br>
                > Gamma Spread: 0.15% (Optimal)
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--text-alert); box-shadow: var(--border-alert);">
            <h2 style="color: var(--text-alert); border-bottom-color: var(--text-alert);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🕴️ Lo Strozzino (Funding Arb)</span> <span class="status-alert">[ONLINE]</span></li>
                <li><span>🧮 Il Contabile (DCA Engine)</span> <span class="status-alert">[ONLINE]</span></li>
                <li><span>🛡️ L'Angelo Custode (MEV Arbitrum)</span> <span class="status-alert blink">[HUNTING]</span></li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--text-alert);">
                > Strozzino APY: 18.4%<br>
                > Angelo Custode Block: #1984201
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr><th>Sensore</th><th>Valore</th><th>Stato</th></tr>
                <tr><td>The Oracle (Sentiment)</td><td>BULLISH (78)</td><td class="status-ok">VALID</td></tr>
                <tr><td>Whale Tracker (Inflow)</td><td>+$45M</td><td class="status-ok">VALID</td></tr>
                <tr><td>Liq. Heatmap</td><td>$68k / $72k</td><td class="status-warn">UPDATING</td></tr>
            </table>
            <div style="margin-top: 10px; font-size: 0.8em;">
                > System Latency: <span id="latency">12</span>ms
            </div>
        </div>
    </div>
    <script>
        setInterval(() => {
            document.getElementById('latency').innerText = Math.floor(Math.random() * 20) + 5;
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
