import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-purple: #b0f;
            --bg-dark: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px currentColor;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 20px;
            color: var(--neon-blue);
            animation: flicker 3s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px var(--neon-green) inset;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px var(--neon-green) inset, 0 0 10px var(--neon-green);
        }
        .panel.trinity {
            border-color: var(--neon-purple);
            box-shadow: 0 0 10px var(--neon-purple) inset;
            color: var(--neon-purple);
        }
        .panel.trinity:hover {
            box-shadow: 0 0 20px var(--neon-purple) inset, 0 0 10px var(--neon-purple);
        }
        .panel.market {
            border-color: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue) inset;
            color: var(--neon-blue);
        }
        .panel.market:hover {
            box-shadow: 0 0 20px var(--neon-blue) inset, 0 0 10px var(--neon-blue);
        }
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1s infinite;
            margin-right: 8px;
        }
        .status.active { background-color: var(--neon-green); box-shadow: 0 0 8px var(--neon-green); }
        .status.warning { background-color: yellow; box-shadow: 0 0 8px yellow; animation: blink 0.5s infinite; }
        .status.offline { background-color: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); animation: none; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin: 15px 0; border-bottom: 1px dashed #333; padding-bottom: 10px;}
        li:last-child { border-bottom: none; }
        
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
            20%, 24%, 55% { text-shadow: none; }
        }
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            font-size: 0.9em;
        }
        .data-cell {
            background: #0a0a0a;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 3px;
            position: relative;
            overflow: hidden;
        }
        .data-cell::after {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.05), transparent);
            transform: skewX(-20deg);
            animation: scanline 3s infinite linear;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status active"></span> ONLINE | SECURE CONNECTION ESTABLISHED</p>
        <p style="color: var(--neon-purple); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span class="status active"></span> <strong>SQUADRA_ALPHA</strong> 🦅<br><span style="color:#aaa; font-size:0.9em;">Target: Binance Scalper | Status: ENGAGING</span></li>
                <li><span class="status active"></span> <strong>SQUADRA_DELTA</strong> 🎯<br><span style="color:#aaa; font-size:0.9em;">Target: Order Flow | Status: MONITORING SPREAD</span></li>
                <li><span class="status active"></span> <strong>SQUADRA_GAMMA</strong> ⚖️<br><span style="color:#aaa; font-size:0.9em;">Target: Bitget Pairs Trading | Status: BALANCING</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p style="font-size: 0.9em; margin-top: -10px; margin-bottom: 20px; color: #888;"><em>Background operations active.</em></p>
            <ul>
                <li><span class="status active"></span> <strong>LO STROZZINO</strong> 🧛‍♂️<br><span style="color:#aaa; font-size:0.9em;">Role: Funding Arb | APY: +14.2%</span></li>
                <li><span class="status active"></span> <strong>IL CONTABILE</strong> 🧮<br><span style="color:#aaa; font-size:0.9em;">Role: Smart DCA | Accumulation: STEADY</span></li>
                <li><span class="status active"></span> <strong>L'ANGELO CUSTODE</strong> 🛡️<br><span style="color:#aaa; font-size:0.9em;">Role: MEV Arbitrum | Protection: ENGAGED</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="data-grid">
                <div class="data-cell">
                    <strong>👁️ THE ORACLE</strong><br>
                    Binance Sentiment<br>
                    <span style="color: var(--neon-green); font-weight: bold; font-size: 1.1em;">BULLISH (78%)</span>
                </div>
                <div class="data-cell">
                    <strong>🐋 WHALE TRACKER</strong><br>
                    Large TX Monitor<br>
                    <span style="color: yellow; font-weight: bold; font-size: 1.1em;">DETECTED ⚠️</span>
                </div>
                <div class="data-cell">
                    <strong>⚡ VOLATILITY IDX</strong><br>
                    Market Turbulence<br>
                    <span style="color: var(--neon-red); font-weight: bold; font-size: 1.1em;">HIGH (4.2%)</span>
                </div>
                <div class="data-cell">
                    <strong>🌐 NETWORK LOAD</strong><br>
                    Eth Gwei Level<br>
                    <span style="color: var(--neon-green); font-weight: bold; font-size: 1.1em;">12 (SAFE)</span>
                </div>
            </div>
            <p style="margin-top:20px; font-size: 0.8em; text-align: center; border-top: 1px dashed #333; padding-top: 10px; color: #666;">Data streams syncing...</p>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const els = document.querySelectorAll('.data-grid .data-cell span');
            els.forEach(el => {
                if(Math.random() > 0.85) {
                    const oldOp = el.style.opacity;
                    el.style.opacity = '0.3';
                    setTimeout(() => el.style.opacity = oldOp || '1', 100);
                }
            });
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Attempt to run on standard port. Will crash if already in use, so wrapper kill is needed.
    app.run(host='0.0.0.0', port=5000, debug=False)
