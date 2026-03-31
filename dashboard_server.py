import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-pink: #ff00ff;
            --neon-blue: #00ffff;
            --bg-dark: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1 { text-align: center; text-shadow: 0 0 10px var(--neon-green); text-transform: uppercase; letter-spacing: 5px; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1200px; margin: auto; }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        .panel h2 {
            color: var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
            text-shadow: 0 0 5px var(--neon-blue);
            margin-top: 0;
        }
        .pink-glow { color: var(--neon-pink) !important; text-shadow: 0 0 5px var(--neon-pink) !important; border-bottom: 1px dashed var(--neon-pink) !important; }
        @keyframes scanline { 100% { left: 200%; } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .status-on { color: #39ff14; animation: blink 2s infinite; font-weight: bold; }
        .status-standby { color: #ffeb3b; animation: blink 3s infinite; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #333; padding: 10px; text-align: left; }
        th { color: var(--neon-pink); background-color: #1a1a1a; }
        td { color: #fff; }
        .indicator-green { color: var(--neon-green); font-weight: bold; }
        .indicator-red { color: #ff003c; font-weight: bold; }
        .indicator-white { color: #fff; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p>⚡ <strong>SQUADRA_ALPHA</strong> (Scalper su Binance): <span class="status-on">[ONLINE - EXEC: 2ms]</span></p>
            <p>🌊 <strong>SQUADRA_DELTA</strong> (Order Flow): <span class="status-on">[ONLINE - READING TAPE]</span></p>
            <p>⚖️ <strong>SQUADRA_GAMMA</strong> (Pairs Trading su Bitget): <span class="status-standby">[STANDBY - WAITING Z-SCORE]</span></p>
        </div>
        
        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="pink-glow">🛡️ PROTOCOLLO TRINITY</h2>
            <p class="status-on">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <p>🦇 <strong>Lo Strozzino</strong> (Funding Arb): <span class="status-on">[ACTIVE - HARVESTING YIELD]</span></p>
            <p>🧮 <strong>Il Contabile</strong> (DCA): <span class="status-on">[ACTIVE - ACCUMULATING BTC]</span></p>
            <p>👼 <strong>L'Angelo Custode</strong> (MEV Arbitrum): <span class="status-on">[ACTIVE - FRONT-RUNNING PROTECTED]</span></p>
        </div>
        
        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO (The Oracle & Whale Tracker)</h2>
            <table>
                <thead>
                    <tr>
                        <th>ASSET</th>
                        <th>SENTIMENT (The Oracle)</th>
                        <th>WHALE FLOW (24h)</th>
                        <th>SIGNAL (Algorithmic)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BTC/USDT</td>
                        <td class="indicator-green">BULLISH 🟢</td>
                        <td class="indicator-green">+ 1,200 BTC Inflow</td>
                        <td>LONG (Conf: 87%)</td>
                    </tr>
                    <tr>
                        <td>ETH/USDT</td>
                        <td class="indicator-white">NEUTRAL ⚪</td>
                        <td class="indicator-red">- 300 ETH Outflow</td>
                        <td>HOLD (Conf: 54%)</td>
                    </tr>
                    <tr>
                        <td>SOL/USDT</td>
                        <td class="indicator-red">EXTREME GREED 🔴</td>
                        <td class="indicator-green">+ 15,000 SOL Inflow</td>
                        <td>SHORT SCALP (Conf: 92%)</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
