from flask import Flask, render_template_string
import threading
import time
import random

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
            --neon-green: #0f0;
            --neon-red: #f00;
            --neon-blue: #0ff;
            --neon-purple: #b026ff;
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
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 1.5s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 15px var(--neon-green);
            border-color: var(--neon-blue);
        }
        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
            margin-top: 0;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            animation: blink 1s infinite;
        }
        .status-warning {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .trinity {
            border-color: var(--neon-purple);
        }
        .trinity h2 {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
            border-bottom-color: var(--neon-purple);
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .progress-bar {
            width: 100%;
            background: #222;
            height: 10px;
            margin-top: 5px;
        }
        .progress {
            height: 100%;
            background: var(--neon-green);
            width: 50%;
            box-shadow: 0 0 5px var(--neon-green);
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        @keyframes flicker {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; text-shadow: none; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid #333;
            padding: 5px;
            text-align: center;
        }
        th {
            color: var(--neon-blue);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND | NUVOLA 🛰️</h1>
        <p>SISTEMA TATTICO QUANTITATIVO - V2.0 // STATO: <span class="status-active">ATTIVO</span></p>
        <p style="font-size: 1.2em; color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA (Scalper Binance)</strong><br>
                    Stato: <span class="status-active">IN INGAGGIO</span> | PNL: +4.2%<br>
                    <div class="progress-bar"><div class="progress" style="width: 85%; background: var(--neon-red);"></div></div>
                </li>
                <li>
                    <strong>🌊 SQUADRA_DELTA (Order Flow)</strong><br>
                    Stato: <span class="status-online">IN ATTESA</span> | PNL: +1.1%<br>
                    <div class="progress-bar"><div class="progress" style="width: 45%;"></div></div>
                </li>
                <li>
                    <strong>⚖️ SQUADRA_GAMMA (Pairs Bitget)</strong><br>
                    Stato: <span class="status-active">ARBITRAGGIO</span> | PNL: +2.8%<br>
                    <div class="progress-bar"><div class="progress" style="width: 60%; background: var(--neon-blue);"></div></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino (Funding Arb)</strong><br>
                    Stato: <span class="status-online">BACKGROUND</span> | APY: 18.5%
                </li>
                <li>
                    <strong>🧮 Il Contabile (DCA)</strong><br>
                    Stato: <span class="status-online">BACKGROUND</span> | Prossimo acquisto: 14h
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode (MEV Arbitrum)</strong><br>
                    Stato: <span class="status-online">SCANSIONE MEMPOOL</span> | Tx Salvate: 14
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>Sorgente</th>
                    <th>Segnale</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance Sent.)</td>
                    <td style="color: var(--neon-red);">BEARISH</td>
                    <td><span class="status-active">LIVE</span></td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td style="color: var(--neon-green);">INFLOW ($45M)</td>
                    <td><span class="status-active">LIVE</span></td>
                </tr>
                <tr>
                    <td>⚡ Liquidity Heatmap</td>
                    <td style="color: var(--neon-blue);">65K CONG</td>
                    <td><span class="status-online">SYNCED</span></td>
                </tr>
            </table>
        </div>
    </div>
    <script>
        // Randomize progress bars slightly to look alive
        setInterval(() => {
            document.querySelectorAll('.progress').forEach(el => {
                let current = parseInt(el.style.width);
                let change = Math.floor(Math.random() * 11) - 5;
                let newWidth = Math.max(10, Math.min(90, current + change));
                el.style.width = newWidth + '%';
            });
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
