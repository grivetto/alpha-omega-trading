import os
from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-magenta: #ff00ff;
            --text-main: #e0e0e0;
            --panel-bg: #111111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan);
            margin-bottom: 30px;
            border-bottom: 1px solid var(--neon-cyan);
            padding-bottom: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid #333;
            padding: 15px;
            border-radius: 5px;
            position: relative;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
        }
        .panel.assault::before { background: linear-gradient(90deg, transparent, var(--neon-magenta), transparent); }
        .panel.trinity::before { background: linear-gradient(90deg, transparent, var(--neon-green), transparent); }
        
        .assault-title { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); }
        .trinity-title { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .metrics-title { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        ul { list-style-type: none; padding: 0; }
        li {
            margin-bottom: 10px;
            padding: 8px;
            background: rgba(255,255,255,0.05);
            border-left: 3px solid #555;
            display: flex;
            justify-content: space-between;
        }
        li.active { border-left-color: var(--neon-green); }
        .status { color: var(--neon-green); font-weight: bold; animation: pulse 2s infinite; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        .scanline {
            position: fixed;
            top: 0; left: 0; right: 0; height: 5px;
            background: rgba(0, 255, 255, 0.2);
            opacity: 0.5;
            pointer-events: none;
            animation: scanline 8s linear infinite;
            z-index: 9999;
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 5px; border-bottom: 1px solid #333; }
        th { color: var(--neon-cyan); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA SYSTEM</h1>
        <p>SYSTEM STATUS: <span style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">ONLINE</span> | UPLINK: SECURE | TIME: ACTIVE</p>
        <p style="font-weight: bold; color: var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- ASSAULT SQUADS -->
        <div class="panel assault">
            <h2 class="assault-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li class="active">
                    <span>🐺 SQUADRA_ALPHA (Scalping / Binance)</span>
                    <span class="status">DEPLOYED</span>
                </li>
                <li class="active">
                    <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                    <span class="status">DEPLOYED</span>
                </li>
                <li class="active">
                    <span>⚖️ SQUADRA_GAMMA (Pairs / Bitget)</span>
                    <span class="status">DEPLOYED</span>
                </li>
            </ul>
        </div>

        <!-- TRINITY PROTOCOL -->
        <div class="panel trinity">
            <h2 class="trinity-title">👁️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li class="active">
                    <span>🕴️ Lo Strozzino (Funding Arb)</span>
                    <span class="status">RUNNING (BG)</span>
                </li>
                <li class="active">
                    <span>💼 Il Contabile (DCA / Rebalance)</span>
                    <span class="status">RUNNING (BG)</span>
                </li>
                <li class="active">
                    <span>🛡️ L'Angelo Custode (MEV / Arbitrum)</span>
                    <span class="status">RUNNING (BG)</span>
                </li>
            </ul>
        </div>

        <!-- METRICS -->
        <div class="panel">
            <h2 class="metrics-title">📊 METRICHE DI MERCATO</h2>
            <p><strong>🔮 THE ORACLE (Sentiment):</strong> <span style="color: var(--neon-cyan);">EXTREME GREED (82)</span></p>
            <p><strong>🐳 WHALE TRACKER:</strong> <span style="color: var(--neon-magenta);">MASSIVE INFLOW DETECTED</span></p>
            <table>
                <tr><th>ASSET</th><th>PRICE</th><th>24H</th><th>SIGNAL</th></tr>
                <tr><td>BTC/USDT</td><td>$108,450.20</td><td style="color: var(--neon-green);">+2.4%</td><td>LONG</td></tr>
                <tr><td>ETH/USDT</td><td>$5,120.80</td><td style="color: var(--neon-green);">+4.1%</td><td>LONG</td></tr>
                <tr><td>ARB/USDT</td><td>$2.85</td><td style="color: #ff3333;">-1.2%</td><td>ACCUMULATE</td></tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return HTML_CONTENT

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
