import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #00ffcc;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px #00ffcc;
            margin-bottom: 10px;
            border-bottom: 1px solid #00ffcc;
            padding-bottom: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(0, 255, 204, 0.05);
            border: 1px solid #00ffcc;
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0,255,204,0.1), 0 0 10px rgba(0,255,204,0.2);
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid #fff; border-left: 2px solid #fff;
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid #fff; border-right: 2px solid #fff;
        }
        .status-online { color: #00ff00; text-shadow: 0 0 5px #00ff00; }
        .status-standby { color: #ffcc00; text-shadow: 0 0 5px #ffcc00; }
        .status-active { color: #ff0055; text-shadow: 0 0 5px #ff0055; animation: blink 1s infinite; }
        ul { list-style: none; padding: 0; }
        li { margin: 10px 0; font-size: 1.1em; }
        @keyframes blink { 50% { opacity: 0.5; } }
        .scanline {
            width: 100%; height: 100vh; z-index: 9999;
            position: fixed; top: 0; left: 0; pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,204,0.1) 50%, rgba(0,0,0,0) 100%);
            background-size: 100% 4px;
        }
        .header { grid-column: 1 / -1; text-align: center; margin-bottom: 20px; }
        .glitch { animation: glitch 3s infinite; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="container">
        <div class="header panel">
            <h1 class="glitch">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
            <p>SYSTEM STATUS: <span class="status-online">OPTIMAL</span> | UPLINK: SECURE | ENCRYPTION: MIL-SPEC</p>
            <p style="font-size: 1.2em; font-weight: bold; color: #00ff00; text-shadow: 0 0 5px #00ff00;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
        </div>

        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>🐺 <b>SQUADRA_ALPHA</b> (Scalper Binance) - <span class="status-active">ENGAGED</span><br><small>Target locked. Execution speed: 4ms.</small></li>
                <li>🦅 <b>SQUADRA_DELTA</b> (Order Flow) - <span class="status-online">MONITORING</span><br><small>Tape reading active. Liquidity identified.</small></li>
                <li>🐍 <b>SQUADRA_GAMMA</b> (Pairs Trading Bitget) - <span class="status-standby">STANDBY</span><br><small>Awaiting divergence threshold.</small></li>
            </ul>
        </div>

        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>🎩 <b>Lo Strozzino</b> (Funding Arb) - <span class="status-online">ONLINE</span><br><small>Harvesting yield. Spread: +0.03%</small></li>
                <li>🧮 <b>Il Contabile</b> (DCA) - <span class="status-online">ONLINE</span><br><small>Accumulation matrix active.</small></li>
                <li>👼 <b>L'Angelo Custode</b> (MEV Arbitrum) - <span class="status-online">ONLINE</span><br><small>Protecting mempool. Slippage nominal.</small></li>
            </ul>
        </div>

        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO (RADAR)</h2>
            <div style="display: flex; justify-content: space-around; text-align: center;">
                <div>
                    <h3>👁️ THE ORACLE (Binance)</h3>
                    <p>FEAR/GREED: <b style="color: #ffcc00;">67</b> (GREED)</p>
                    <p>LONG/SHORT RATIO: <span class="status-online">1.14</span></p>
                </div>
                <div>
                    <h3>🐋 WHALE TRACKER</h3>
                    <p>LAST ALERT: 5,000 ETH -> CEX</p>
                    <p>IMPACT PROB: <span class="status-active">HIGH</span></p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
