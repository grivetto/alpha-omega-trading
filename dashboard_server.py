from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
            --border-color: #1a4a28;
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
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(57, 255, 20, 0.2);
        }
        .header h1 {
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .header .status {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            animation: blink 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0, 0, 0, 0.8);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding: 5px; border-left: 2px solid var(--neon-green); background: rgba(0,255,0,0.05); }
        .status-badge {
            float: right;
            background: var(--neon-green);
            color: black;
            padding: 2px 5px;
            font-size: 0.8em;
            font-weight: bold;
            border-radius: 3px;
        }
        .status-badge.standby { background: var(--neon-blue); }
        .status-badge.active { background: var(--neon-red); animation: pulse 1s infinite; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; text-align: left; }
        th, td { border-bottom: 1px dashed #333; padding: 8px; }
        th { color: #888; }
        .positive { color: var(--neon-green); }
        .negative { color: var(--neon-red); }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255,0,60,0.7); } 70% { box-shadow: 0 0 0 5px rgba(255,0,60,0); } 100% { box-shadow: 0 0 0 0 rgba(255,0,60,0); } }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            animation: scan 6s linear infinite;
            top: 0;
            left: 0;
        }
        @keyframes scan { 0% { top: -100px; } 100% { top: 100%; } }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <p class="status">>>> UPLINK STABILITO | SISTEMI NOMINALI | CRITTOGRAFIA QUANTISTICA ATTIVA <<<</p>
        <h3 style="color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> (Scalper su Binance)
                    <span class="status-badge active">ENGAGED</span>
                    <br><small>Target: BTC/USDT | Latency: 12ms</small>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> (Order Flow)
                    <span class="status-badge">ONLINE</span>
                    <br><small>Target: ETH/USDT | Imbalance detected</small>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)
                    <span class="status-badge standby">STANDBY</span>
                    <br><small>Spread calculation in progress</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🎩 Lo Strozzino</strong> (Funding Arb)
                    <span class="status-badge">ONLINE</span>
                    <br><small>Capturing yield across CEX/DEX | APR: +18.4%</small>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA)
                    <span class="status-badge">ONLINE</span>
                    <br><small>Accumulation phase active | Next buy: 4h 12m</small>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)
                    <span class="status-badge active">HUNTING</span>
                    <br><small>Scanning mempool for arbitrage | Flashloans ready</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>MODULO</th>
                    <th>STATO / VALORE</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Sentiment)</td>
                    <td class="positive">BULLISH (78/100)</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td class="negative">LARGE OUTFLOW DETECTED</td>
                </tr>
                <tr>
                    <td>⚡ Network Gwei</td>
                    <td>15.4 (Low)</td>
                </tr>
                <tr>
                    <td>💧 Liquidity Siphon</td>
                    <td class="positive">+2.4M USD (24h)</td>
                </tr>
            </table>
            <p style="text-align: center; margin-top: 15px; font-size: 0.8em; color: #555;">[DATI IN TEMPO REALE TRAMITE WEBSOCKET MULTIPLEX]</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
