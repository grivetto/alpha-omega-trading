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
            --bg-color: #050505;
            --neon-green: #00ff00;
            --neon-cyan: #00ffff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff0033;
            --grid-color: rgba(0, 255, 0, 0.1);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 20px 20px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-bottom: 10px;
            border-bottom: 1px solid var(--neon-green);
            padding-bottom: 5px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
            animation: glitch 1.5s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid var(--neon-green);
            padding: 15px;
            background: rgba(0, 20, 0, 0.5);
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            animation: scanline 3s linear infinite;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-active {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
        }
        .status-danger {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .item {
            margin: 10px 0;
            display: flex;
            justify-content: space-between;
        }
        .magenta-glow {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
        }
        @keyframes scanline {
            0% { top: 0; }
            100% { top: 100%; }
        }
        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid rgba(0, 255, 0, 0.3);
            padding: 5px;
            text-align: left;
        }
        th {
            background: rgba(0, 255, 0, 0.1);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> // SECURE CONNECTION ESTABLISHED</p>
        <p class="magenta-glow" style="margin-top: 5px; font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) ⚔️</h2>
            <div class="item">
                <span>[ALPHA] Scalper (Binance)</span>
                <span class="status-active">ENGAGED 🟢</span>
            </div>
            <p>Target: Volatility | PnL: +2.4% | Ping: 12ms</p>
            <hr style="border-color: rgba(0,255,0,0.3)">
            
            <div class="item">
                <span>[DELTA] Order Flow</span>
                <span class="status-active">MONITORING 🔵</span>
            </div>
            <p>Target: Liquidity Grabs | Books: Synced</p>
            <hr style="border-color: rgba(0,255,0,0.3)">
            
            <div class="item">
                <span>[GAMMA] Pairs Trading (Bitget)</span>
                <span class="status-online">STANDBY 🟡</span>
            </div>
            <p>Target: Spread Reversion | Z-Score: 1.2</p>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="magenta-glow">🔺 PROTOCOLLO TRINITY 🔺</h2>
            <div class="item">
                <span>💰 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">ACTIVE [BKG]</span>
            </div>
            <p>Delta Neutral | APR: 14.2%</p>
            <hr style="border-color: rgba(0,255,0,0.3)">
            
            <div class="item">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">ACTIVE [BKG]</span>
            </div>
            <p>Accumulation: BTC, ETH | Next execution: 14h</p>
            <hr style="border-color: rgba(0,255,0,0.3)">
            
            <div class="item">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">ACTIVE [BKG]</span>
            </div>
            <p>Flashbots RPC | Searching for sandwiches 🥪</p>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div style="display: flex; gap: 20px;">
                <div style="flex: 1;">
                    <h3>👁️ THE ORACLE (Binance Sentiment)</h3>
                    <table>
                        <tr><th>Asset</th><th>Sentiment</th><th>Signal</th></tr>
                        <tr><td>BTC/USDT</td><td>Bullish (68%)</td><td class="status-active">LONG</td></tr>
                        <tr><td>ETH/USDT</td><td>Neutral (51%)</td><td>HOLD</td></tr>
                        <tr><td>SOL/USDT</td><td class="status-danger">Overbought (88%)</td><td class="status-danger">SHORT</td></tr>
                    </table>
                </div>
                <div style="flex: 1;">
                    <h3>🐋 WHALE TRACKER</h3>
                    <table>
                        <tr><th>Time</th><th>Tx Value</th><th>Network</th></tr>
                        <tr><td>-2m</td><td class="status-danger">12,450 ETH</td><td>Ethereum</td></tr>
                        <tr><td>-15m</td><td class="status-active">450 BTC</td><td>Bitcoin</td></tr>
                        <tr><td>-42m</td><td>$50M USDT</td><td>Tron</td></tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 20px; font-size: 0.8em; opacity: 0.5;">
        <p>UNAUTHORIZED ACCESS WILL BE TERMINATED. HAVE A NICE DAY.</p>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
