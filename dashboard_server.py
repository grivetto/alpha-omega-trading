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
    <title>ORBITAL COMMAND - Nuvola</title>
    <style>
        :root {
            --bg: #050505;
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-red: #ff073a;
            --neon-yellow: #f3f315;
            --panel-bg: rgba(10, 20, 15, 0.8);
            --border: 1px solid #113322;
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-cyan);
            animation: pulse-cyan 2s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: var(--border);
            padding: 15px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.red::before {
            background: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red);
        }
        .panel.cyan::before {
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
        }
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }
        .status.offline {
            background: var(--neon-red);
            box-shadow: 0 0 8px var(--neon-red);
            animation: none;
        }
        .status.idle {
            background: var(--neon-yellow);
            box-shadow: 0 0 8px var(--neon-yellow);
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            border-bottom: 1px dashed #225533;
            padding-bottom: 5px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            background: rgba(0, 255, 255, 0.05);
            border: 1px solid #044;
            padding: 10px;
            text-align: center;
        }
        .metric-value {
            font-size: 1.5em;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
        }
        
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        @keyframes pulse-cyan {
            0% { text-shadow: 0 0 5px var(--neon-cyan); }
            50% { text-shadow: 0 0 20px var(--neon-cyan); }
            100% { text-shadow: 0 0 5px var(--neon-cyan); }
        }
        
        /* CRT Scanline effect */
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
            z-index: 9999;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND - NUVOLA NODE 🛰️</h1>
        <p>SYSTEM STATUS: <span style="color:var(--neon-green)">ONLINE</span> | UPLINK: SECURE | TACTICAL VIEW</p>
        <div style="margin-top: 10px; font-weight: bold; color: var(--neon-cyan); border: 1px dashed var(--neon-cyan); display: inline-block; padding: 5px 15px; background: rgba(0,255,255,0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="status"></span> <strong>SQUADRA_ALPHA</strong> 🦅
                    <br><small>Target: Binance | Strategy: Micro-Scalping</small>
                    <br><span style="color:var(--neon-green)">[ACTV] High-Frequency sweeps engaged. Win rate: 68.4%</span>
                </li>
                <li>
                    <span class="status"></span> <strong>SQUADRA_DELTA</strong> 🎯
                    <br><small>Target: Multi-Dex | Strategy: Order Flow Imbalance</small>
                    <br><span style="color:var(--neon-green)">[ACTV] Tracking institutional tape.</span>
                </li>
                <li>
                    <span class="status idle"></span> <strong>SQUADRA_GAMMA</strong> ⚖️
                    <br><small>Target: Bitget | Strategy: Statistical Pairs Trading</small>
                    <br><span style="color:var(--neon-yellow)">[STBY] Waiting for divergence Z-score > 2.5</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel cyan">
            <h2 style="color:var(--neon-cyan)">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span class="status"></span> <strong>LO STROZZINO</strong> 🧛‍♂️
                    <br><small>Role: Funding Rate Arbitrage</small>
                    <br><span style="color:var(--neon-cyan)">[BKGND] Harvesting negative funding on perps.</span>
                </li>
                <li>
                    <span class="status"></span> <strong>IL CONTABILE</strong> 🧮
                    <br><small>Role: Dynamic DCA & Rebalancing</small>
                    <br><span style="color:var(--neon-cyan)">[BKGND] Accumulating dips > 5% variance.</span>
                </li>
                <li>
                    <span class="status"></span> <strong>L'ANGELO CUSTODE</strong> 🛡️
                    <br><small>Role: Arbitrum MEV Protection / Flashbots</small>
                    <br><span style="color:var(--neon-cyan)">[BKGND] Shielding transactions, sniffing mempool.</span>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel red">
            <h2 style="color:var(--neon-red)">📡 INTEL & RADAR (METRICHE)</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>THE ORACLE 🔮</div>
                    <small>Binance Sentiment</small>
                    <div class="metric-value">BULLISH 72%</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER 🐋</div>
                    <small>Large Tx/h</small>
                    <div class="metric-value">1,204 Tx</div>
                </div>
                <div class="metric-box">
                    <div>GLOBAL LIQUIDITY 💧</div>
                    <small>M2 Proxy</small>
                    <div class="metric-value">+1.2%</div>
                </div>
                <div class="metric-box">
                    <div>VOLATILITY INDEX ⚡</div>
                    <small>Crypto VIX</small>
                    <div class="metric-value">64.5 (HIGH)</div>
                </div>
            </div>
            <p style="text-align:center; font-size:0.8em; margin-top:20px; color:#666;">
                > INTERCEPTING ON-CHAIN DATA... [OK]<br>
                > DECRYPTING ORDER BOOKS... [OK]
            </p>
        </div>
    </div>
    
    <script>
        // Placeholder per finti aggiornamenti in tempo reale
        setInterval(() => {
            const values = document.querySelectorAll('.metric-value');
            if(Math.random() > 0.7) {
                values[1].innerText = (1200 + Math.floor(Math.random() * 50)) + " Tx";
            }
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start on port 5000 or similar
    app.run(host='0.0.0.0', port=5000, debug=False)
