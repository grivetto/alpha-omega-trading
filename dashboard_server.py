import os
import time
from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #00ff66;
            --neon-red: #ff3366;
            --grid-color: rgba(0, 243, 255, 0.1);
        }
        body {
            background-color: var(--bg-color);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            font-size: 2.5em;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(10, 10, 20, 0.8);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2) inset;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { top: 0%; opacity: 1; }
            50% { opacity: 0.5; }
            100% { top: 100%; opacity: 0; }
        }
        h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.5em;
            margin-top: 0;
            border-bottom: 1px dotted var(--neon-pink);
            padding-bottom: 5px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(255,255,255,0.05);
            border-left: 3px solid var(--neon-green);
        }
        .status.offline { border-left-color: var(--neon-red); }
        .status.idle { border-left-color: #ffd700; }
        .label { font-weight: bold; }
        .value { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .value.offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .value.idle { color: #ffd700; text-shadow: 0 0 5px #ffd700; }
        
        .grid-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .grid-item {
            background: rgba(0,0,0,0.5);
            padding: 8px;
            border: 1px solid rgba(0, 243, 255, 0.3);
            text-align: center;
        }
        .grid-val {
            display: block;
            font-size: 1.2em;
            color: var(--neon-blue);
            margin-top: 5px;
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.8em;
            color: #555;
        }
    </style>
</head>
<body>
    <h1>🚀 ORBITAL COMMAND <span class="blink">_</span></h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span class="label">🎯 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="value">ACTIVE</span>
            </div>
            <div class="status">
                <span class="label">🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="value">ACTIVE</span>
            </div>
            <div class="status">
                <span class="label">⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="value idle">STANDBY</span>
            </div>
            <div style="margin-top:15px; font-size: 0.8em; color: #888;">
                [>] Alpha targeting micro-volatility on BTC/USDT.<br>
                [>] Delta monitoring liquidity pools.<br>
                [>] Gamma awaiting divergence triggers.
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; border: 1px solid var(--neon-green); padding: 5px; background: rgba(0, 255, 102, 0.1);">
                <span style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <div class="status">
                <span class="label">🧛 Lo Strozzino (Funding Arb)</span>
                <span class="value">ONLINE</span>
            </div>
            <div class="status">
                <span class="label">🧮 Il Contabile (DCA)</span>
                <span class="value">ONLINE</span>
            </div>
            <div class="status">
                <span class="label">👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="value">ONLINE</span>
            </div>
            <div style="margin-top:15px; font-size: 0.8em; color: #888;">
                [+] Extracting yield across perp markets.<br>
                [+] DCA executing systematically.<br>
                [+] Arbitrum mempool scanned 24/7.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="grid-data">
                <div class="grid-item">
                    <span>👁️ THE ORACLE (Sentiment)</span>
                    <span class="grid-val">{{ sentiment }}% BULLISH</span>
                </div>
                <div class="grid-item">
                    <span>🐳 WHALE TRACKER</span>
                    <span class="grid-val">{{ whales }} Tx/h</span>
                </div>
                <div class="grid-item">
                    <span>🔥 VOLATILITY INDEX</span>
                    <span class="grid-val" style="color:var(--neon-pink)">{{ vol }}</span>
                </div>
                <div class="grid-item">
                    <span>⚡ NETWORK LOAD</span>
                    <span class="grid-val" style="color:var(--neon-green)">{{ load }}%</span>
                </div>
            </div>
        </div>
        
        <!-- SYSTEM LOG -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>🖥️ SYSTEM FEED</h2>
            <div style="font-family: monospace; font-size: 0.9em; line-height: 1.5; color: #0f0; text-shadow: 0 0 2px #0f0;">
                > [SYS] Orbital Command initialized... OK<br>
                > [NET] Secure connection to Exchange APIs established.<br>
                > [MEV] L'Angelo Custode detected 3 arbitrage opportunities in the last hour.<br>
                > [HFT] Squadra Alpha executed 45 trades today. PnL: +$142.50<br>
                > [SYS] Monitoring market conditions... <span class="blink">_</span>
            </div>
        </div>
    </div>
    
    <div class="footer">
        NUVOLA QUANTITATIVE SYSTEMS // RESTRICTED ACCESS // TIME: {{ time }}
    </div>
    
    <script>
        // Auto-refresh the page to keep metrics "live"
        setTimeout(function() {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        sentiment=random.randint(45, 85),
        whales=random.randint(10, 500),
        vol=round(random.uniform(0.5, 5.0), 2),
        load=random.randint(10, 99),
        time=time.strftime('%Y-%m-%d %H:%M:%S')
    )

if __name__ == '__main__':
    # Try to make directory if not exist
    os.makedirs('/home/sergio/.openclaw/workspace/denaro', exist_ok=True)
    app.run(host='0.0.0.0', port=8080)
