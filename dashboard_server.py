import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-color: #00ffcc;
            --accent-color: #ff0055;
            --glow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
            --glow-alert: 0 0 10px #ff0055, 0 0 20px #ff0055;
            --panel-bg: rgba(0, 20, 40, 0.6);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 204, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 204, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            margin-top: 0;
        }
        h1 {
            text-align: center;
            text-shadow: var(--glow);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--text-color);
            padding-bottom: 10px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--text-color);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0, 255, 204, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--text-color);
            box-shadow: var(--glow);
        }
        .panel.alert::before {
            background: var(--accent-color);
            box-shadow: var(--glow-alert);
        }
        .panel.alert {
            border-color: var(--accent-color);
            color: var(--accent-color);
        }
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: #00ffcc;
            box-shadow: var(--glow);
            animation: blink 1.5s infinite alternate;
            margin-right: 10px;
        }
        .status-indicator.bg {
            background-color: #aaa;
            box-shadow: 0 0 10px #aaa;
            animation: pulse 3s infinite alternate;
        }
        @keyframes blink {
            0% { opacity: 0.5; box-shadow: 0 0 5px #00ffcc; }
            100% { opacity: 1; box-shadow: 0 0 20px #00ffcc; }
        }
        @keyframes pulse {
            0% { opacity: 0.3; }
            100% { opacity: 0.8; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid rgba(0, 255, 204, 0.3);
            padding: 8px;
            text-align: left;
        }
        th {
            background: rgba(0, 255, 204, 0.1);
        }
        .data-row {
            font-size: 0.9em;
            margin-bottom: 8px;
        }
        .data-row span.right {
            float: right;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h1><span class="status-indicator"></span> ORBITAL COMMAND TERMINAL v3.0 📡</h1>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <p>⚡ <b>SQUADRA_ALPHA</b> [Scalper Binance] <span class="right">ONLINE <span class="status-indicator"></span></span></p>
                <p>🎯 <b>SQUADRA_DELTA</b> [Order Flow] <span class="right">ONLINE <span class="status-indicator"></span></span></p>
                <p>⚖️ <b>SQUADRA_GAMMA</b> [Pairs Trading Bitget] <span class="right">ONLINE <span class="status-indicator"></span></span></p>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <p><i>Background Services Active</i><br><span style="color: #ff0055; font-weight: bold; text-shadow: 0 0 5px #ff0055;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></p>
            <div class="data-row">
                <p>🕴️ <b>Lo Strozzino</b> (Funding Arb) <span class="right"><span class="status-indicator bg"></span> ACTIVE</span></p>
                <p>🧮 <b>Il Contabile</b> (DCA) <span class="right"><span class="status-indicator bg"></span> ACTIVE</span></p>
                <p>👼 <b>L'Angelo Custode</b> (MEV Arbitrum) <span class="right"><span class="status-indicator bg"></span> ACTIVE</span></p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <thead>
                    <tr>
                        <th>Modulo</th>
                        <th>Target</th>
                        <th>Status / Dati</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>👁️ The Oracle</td>
                        <td>Binance Sentiment</td>
                        <td style="color: #00ffcc;">BULLISH [78%]</td>
                    </tr>
                    <tr>
                        <td>🐋 Whale Tracker</td>
                        <td>On-Chain Anomaly</td>
                        <td style="color: var(--accent-color);">ALERT: 50M USDT Move</td>
                    </tr>
                    <tr>
                        <td>🌐 Network</td>
                        <td>Latencies</td>
                        <td>12ms avg</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- SYSTEM STATUS -->
        <div class="panel alert">
            <h2>⚠️ ALERT SYSTEM</h2>
            <p>NUVOLA CORE INTERFACE SECURED.</p>
            <p>QUANTITATIVE MILITARY HUD ENABLED.</p>
            <p>LAST SYNC: <span id="clock"></span></p>
        </div>
    </div>

    <script>
        function updateTime() {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
        setInterval(updateTime, 1000);
        updateTime();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue sulla porta 5000 in tutte le interfacce
    app.run(host='0.0.0.0', port=5000, debug=False)
