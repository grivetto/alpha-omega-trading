import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

# Tactical cyberpunk HTML/CSS template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --bg-dark: #0a0a0a;
            --panel-bg: rgba(10, 20, 30, 0.85);
            --grid-color: rgba(0, 243, 255, 0.1);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            text-shadow: 0 0 5px var(--neon-blue);
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 0;
            margin-bottom: 15px;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px rgba(0, 243, 255, 0.5);
        }

        .title {
            font-size: 2.5em;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            animation: pulse 2s infinite;
        }

        .subtitle {
            font-size: 1em;
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            padding: 25px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.3), 0 0 25px rgba(0, 243, 255, 0.5);
            transform: translateY(-2px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-pink);
            box-shadow: 0 0 10px var(--neon-pink);
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px dashed rgba(0, 243, 255, 0.3);
            padding: 12px 0;
            font-size: 0.95em;
        }

        .stat-desc {
            font-size: 0.8em;
            color: #888;
            padding-bottom: 10px;
            margin-top: -5px;
            display: block;
        }

        .status {
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.9em;
            letter-spacing: 1px;
            text-shadow: none;
            color: #000;
        }
        
        .status.online { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); animation: blink 2s infinite; }
        .status.active { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .status.standby { background: #ffaa00; box-shadow: 0 0 10px #ffaa00; }

        .trinity-banner {
            margin-top: 15px;
            padding: 10px;
            border: 1px solid var(--neon-green);
            color: var(--neon-green);
            background: rgba(57, 255, 20, 0.05);
            font-weight: bold;
            display: inline-block;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2), 0 0 15px rgba(57, 255, 20, 0.3);
            text-shadow: 0 0 5px var(--neon-green);
        }

        .log-window {
            height: 180px;
            overflow-y: hidden;
            font-size: 0.85em;
            color: #00f3ff;
            background: rgba(0,0,0,0.8);
            border: 1px solid #333;
            padding: 15px;
            margin-top: 20px;
            position: relative;
        }
        
        .log-window::after {
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(rgba(0,0,0,0) 50%, rgba(0,0,0,0.25) 50%);
            background-size: 100% 4px;
            pointer-events: none;
        }

        .log-line { margin: 4px 0; font-family: monospace; opacity: 0.8; }
        .log-line.alert { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .log-line.success { color: var(--neon-green); }

        @keyframes pulse {
            0% { opacity: 0.8; text-shadow: 0 0 10px var(--neon-blue); }
            50% { opacity: 1; text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
            100% { opacity: 0.8; text-shadow: 0 0 10px var(--neon-blue); }
        }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">🛰️ ORBITAL COMMAND 🛰️</div>
        <div class="subtitle">QUANTITATIVE TRADING TERMINAL [NUVOLA v4.0]</div>
        <div class="trinity-banner">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            
            <div class="stat-row">
                <span>🐺 SQUADRA_ALPHA <br><small>[Scalper Binance]</small></span>
                <span class="status online">ONLINE</span>
            </div>
            <span class="stat-desc">↳ APM: 420 | PnL (24h): +1.24% | Liquidity: Nominal</span>

            <div class="stat-row">
                <span>🌊 SQUADRA_DELTA <br><small>[Order Flow]</small></span>
                <span class="status active">ENGAGED</span>
            </div>
            <span class="stat-desc">↳ Imbalance detect: HIGH | Open Positions: 4</span>

            <div class="stat-row">
                <span>⚖️ SQUADRA_GAMMA <br><small>[Pairs Trading Bitget]</small></span>
                <span class="status active">ACTIVE</span>
            </div>
            <span class="stat-desc">↳ Z-Score: 2.1 | Spread Arb: Running | Exposure: Delta-Neutral</span>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">♅ PROTOCOLLO TRINITY</h2>
            
            <div class="stat-row">
                <span>🎩 Lo Strozzino <br><small>[Funding Arb]</small></span>
                <span class="status standby">MONITORING</span>
            </div>
            <span class="stat-desc">↳ Yield target: >15% APR | Scanning Perpetual Spreads</span>

            <div class="stat-row">
                <span>🧮 Il Contabile <br><small>[DCA & Accumulation]</small></span>
                <span class="status online">BACKGROUND</span>
            </div>
            <span class="stat-desc">↳ Accruing BTC/ETH on localized support | Reserve: Healthy</span>

            <div class="stat-row">
                <span>🛡️ L'Angelo Custode <br><small>[MEV Arbitrum]</small></span>
                <span class="status online">PATROLLING</span>
            </div>
            <span class="stat-desc">↳ Flashbots RPC connected | Sandwich Defense ON</span>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">📊 MARKET METRICS</h2>
            
            <div class="stat-row">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span class="status active" id="oracle-val">BULLISH [0.68]</span>
            </div>
            <div class="stat-row">
                <span>🐋 Whale Tracker</span>
                <span class="status standby">ALERT: 2K BTC</span>
            </div>
            <div class="stat-row">
                <span>⚡ Nuvola-VIX (Volatility)</span>
                <span class="status online">ELEVATED [42.1]</span>
            </div>
            
            <div class="log-window" id="terminal">
                <div class="log-line">> [SYS] Initializing tactical layout... OK</div>
                <div class="log-line success">> [SYS] Secure connection established with Nuvola Node.</div>
                <div class="log-line">> [ALPHA] Executed LIMIT BUY BTCUSDT @ 65400</div>
                <div class="log-line alert">> [ORACLE] Sudden volume spike detected on SOL!</div>
                <div class="log-line">> [GAMMA] Rebalancing pair ETH/SOL</div>
                <div class="log-line">> [STROZZINO] Divergence found: Bybit vs Binance.</div>
            </div>
        </div>
    </div>

    <script>
        // Simulate real-time terminal and metric updates
        const oracle = document.getElementById('oracle-val');
        const vals = ['BULLISH [0.68]', 'BULLISH [0.69]', 'NEUTRAL [0.55]', 'BULLISH [0.71]', 'BEARISH [0.42]'];
        setInterval(() => {
            oracle.innerText = vals[Math.floor(Math.random() * vals.length)];
        }, 3500);

        const term = document.getElementById('terminal');
        const logs = [
            "> [DELTA] Absorbing sell wall...",
            "> [ANGELO] Blocked sandwich attack on ARB.",
            "> [CONTABILE] DCA executed: 0.05 BTC.",
            "> [ALPHA] Trailing stop updated.",
            "> [SYS] Latency check: 12ms",
            "> [WHALE] Large transfer: 50M USDT to Binance."
        ];
        setInterval(() => {
            const div = document.createElement('div');
            div.className = 'log-line';
            if (Math.random() > 0.8) div.classList.add('alert');
            else if (Math.random() > 0.8) div.classList.add('success');
            div.innerText = logs[Math.floor(Math.random() * logs.length)];
            term.appendChild(div);
            if (term.children.length > 8) {
                term.removeChild(term.firstChild);
            }
        }, 4000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

if __name__ == '__main__':
    # Start Nuvola Orbital Command Dashboard
    app.run(host='0.0.0.0', port=5000, debug=False)