import os
import time
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND ⚡ NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff073a;
            --neon-purple: #bc13fe;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px currentColor;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        h1 { color: var(--neon-blue); text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; margin-bottom: 30px;}
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }
        @keyframes blink {
            from { opacity: 1; }
            to { opacity: 0.3; }
        }
        .module { margin-bottom: 15px; border-left: 3px solid var(--neon-blue); padding-left: 10px; }
        .module-title { color: var(--neon-blue); font-weight: bold; }
        
        .red-glow { border-color: var(--neon-red); }
        .red-glow h2 { color: var(--neon-red); }
        
        .purple-glow { border-color: var(--neon-purple); }
        .purple-glow h2 { color: var(--neon-purple); }
        .purple-glow .status-indicator { background-color: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .purple-glow .module-title { color: var(--neon-purple); border-color: var(--neon-purple); }

        .data-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px;}
        .data-cell { background: #000; border: 1px solid #333; padding: 10px; text-align: center; font-size: 0.9em; }
        .data-val { font-size: 1.2em; font-weight: bold; margin-top: 5px; color: #fff; text-shadow: 0 0 5px #fff; }
        .up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .warn { color: #ffa500; text-shadow: 0 0 5px #ffa500; }
        
        /* Glitch effect for title */
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2s infinite linear alternate-reverse;
        }
        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 44px, 0); }
            20% { clip: rect(74px, 9999px, 86px, 0); }
            40% { clip: rect(14px, 9999px, 20px, 0); }
            60% { clip: rect(54px, 9999px, 66px, 0); }
            80% { clip: rect(98px, 9999px, 11px, 0); }
            100% { clip: rect(2px, 9999px, 18px, 0); }
        }
    </style>
</head>
<body>
    <h1 class="glitch" data-text="⚡ ORBITAL COMMAND // NUVOLA ⚡">⚡ ORBITAL COMMAND // NUVOLA ⚡</h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>SQUADRA_ALPHA 🐺 [Binance Scalper]</div>
                <div>Target: BTC/USDT, ETH/USDT | Latency: 12ms | Win Rate: 68.4%</div>
                <div>Status: <span style="color:var(--neon-green)">ENGAGED</span> - Executing micro-buys on support</div>
            </div>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>SQUADRA_DELTA 🦅 [Order Flow]</div>
                <div>Target: Binance Futures | Latency: 18ms | Volume Imbalance: Detected</div>
                <div>Status: <span style="color:var(--neon-green)">ENGAGED</span> - Front-running spoofed orders</div>
            </div>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>SQUADRA_GAMMA 🐍 [Bitget Pairs Trading]</div>
                <div>Target: SOL/USDT vs AVAX/USDT | Z-Score: > 2.5</div>
                <div>Status: <span style="color:var(--neon-green)">ENGAGED</span> - Mean reversion active</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple-glow">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div style="background-color: #220033; border: 1px solid var(--neon-purple); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; color: var(--neon-purple);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>LO STROZZINO 🕴️ [Funding Arb]</div>
                <div>Mode: Delta-Neutral | Spread: 0.045% / 8h</div>
                <div>Status: <span style="color:var(--neon-purple)">ONLINE</span> - Harvesting yield</div>
            </div>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>IL CONTABILE 🧮 [Smart DCA]</div>
                <div>Mode: Accumulation | Assets: BTC, SOL | Trigger: RSI < 35</div>
                <div>Status: <span style="color:var(--neon-purple)">ONLINE</span> - Waiting for dip</div>
            </div>
            <div class="module">
                <div class="module-title"><span class="status-indicator"></span>L'ANGELO CUSTODE 🛡️ [Arbitrum MEV]</div>
                <div>Mode: Sandwich/Snipe | Mempool: Scanning...</div>
                <div>Status: <span style="color:var(--neon-purple)">ONLINE</span> - Protecting txs & extracting value</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel red-glow" style="grid-column: 1 / -1;">
            <h2>📊 THE ORACLE // WHALE TRACKER</h2>
            <div class="data-grid">
                <div class="data-cell">
                    <div>BINANCE SENTIMENT (AI)</div>
                    <div class="data-val up">BULLISH 🟢 78%</div>
                </div>
                <div class="data-cell">
                    <div>WHALE WALLET MOVEMENT</div>
                    <div class="data-val down">OUTFLOW 🔴 $142M</div>
                </div>
                <div class="data-cell">
                    <div>LIQUIDATION HEATMAP</div>
                    <div class="data-val warn">SHORT SQUEEZE ⚠️ 68K</div>
                </div>
                <div class="data-cell">
                    <div>GLOBAL FUNDING RATE</div>
                    <div class="data-val up">+0.015% 🟢</div>
                </div>
                <div class="data-cell">
                    <div>VOLATILITY INDEX (VIX)</div>
                    <div class="data-val warn">ELEVATED ⚠️ 42.1</div>
                </div>
                <div class="data-cell">
                    <div>TOTAL SYSTEM PNL (1h)</div>
                    <div class="data-val up">+$1,337.42 🟢</div>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #666; text-align: right;">
                > SYSTEM NOMINAL... ALL SYSTEMS OPERATIONAL.
            </div>
        </div>
    </div>
    
    <script>
        // Blinking numbers simulation
        setInterval(() => {
            const pnl = document.querySelectorAll('.data-val.up')[2];
            if(pnl) {
                let current = parseFloat(pnl.innerText.replace('+$', '').replace(' 🟢', '').replace(',', ''));
                current += (Math.random() * 2 - 1);
                pnl.innerText = '+$' + current.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + ' 🟢';
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
    app.run(host='0.0.0.0', port=5000, debug=False)
