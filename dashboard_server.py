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
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-purple: #bc13fe;
            --neon-red: #ff073a;
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
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px currentColor, 0 0 10px currentColor;
        }
        h1 { color: var(--neon-cyan); text-align: center; border-bottom: 2px solid var(--neon-cyan); padding-bottom: 10px; }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.5);
            border-color: var(--neon-cyan);
        }
        .panel h2 {
            margin-top: 0;
            color: var(--neon-purple);
            border-bottom: 1px dashed var(--neon-purple);
            padding-bottom: 5px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(255, 255, 255, 0.05);
        }
        .online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 2s infinite; }
        .offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .data-box {
            border: 1px solid var(--neon-cyan);
            padding: 5px;
            text-align: center;
        }
        .data-val {
            font-size: 1.2em;
            font-weight: bold;
            color: var(--neon-cyan);
        }
        .alert {
            color: var(--neon-red);
            border: 1px solid var(--neon-red);
            padding: 10px;
            margin-top: 20px;
            text-align: center;
            text-shadow: 0 0 5px var(--neon-red);
            box-shadow: 0 0 10px rgba(255, 7, 58, 0.3);
            animation: blink 1s infinite;
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA TERMINAL</h1>
    
    <div style="text-align: center; font-size: 1.2em; margin-bottom: 20px; color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); border: 1px solid var(--neon-cyan); padding: 10px; background: rgba(0, 255, 255, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="active">[ ENGAGED ]</span>
            </div>
            <div class="status">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="active">[ MONITORING ]</span>
            </div>
            <div class="status">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="active">[ ARB HUNT ]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Last execution latency: 12ms<br>
                > Alpha PnL (24h): +4.2%<br>
                > Gamma targets: BTC/ETH, SOL/ADA
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status">
                <span>💼 Lo Strozzino (Funding Arb)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span>🧮 Il Contabile (DCA Grid)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span>🛡️ L'Angelo Custode (MEV Arb)</span>
                <span class="online">[ ONLINE ]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                > Strozzino APY: 18.4% (Binance/Bybit)<br>
                > Contabile phase: Accumulation (BTC)<br>
                > Angelo Custode status: Mempool Scanning
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="data-grid">
                <div class="data-box">
                    <div>The Oracle (Sent)</div>
                    <div class="data-val" style="color: var(--neon-green)">BULLISH 72%</div>
                </div>
                <div class="data-box">
                    <div>Whale Tracker</div>
                    <div class="data-val" style="color: var(--neon-red)">SELL WALL</div>
                </div>
                <div class="data-box">
                    <div>Global Volatility</div>
                    <div class="data-val">HIGH</div>
                </div>
                <div class="data-box">
                    <div>Liq. Heatmap</div>
                    <div class="data-val">68k / 71k</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="alert">
        SYSTEM SECURE. ALL SUB-ROUTINES NOMINAL. WELCOME BACK, COMMANDER.
    </div>
    
    <script>
        // Randomly update values to look alive
        setInterval(() => {
            const vol = document.querySelectorAll('.data-val')[2];
            vol.innerText = Math.random() > 0.5 ? 'HIGH' : 'EXTREME';
            vol.style.color = vol.innerText === 'EXTREME' ? 'var(--neon-red)' : 'var(--neon-cyan)';
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
