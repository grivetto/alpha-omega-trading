import os
from flask import Flask, render_template_string
import threading

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
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 30, 0.8);
            --border-color: #0ff;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-shadow: 0 0 5px var(--neon-cyan);
        }
        h1, h2, h3 {
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 2px;
            animation: glitch 2.5s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            box-shadow: 0 0 10px var(--border-color), inset 0 0 10px var(--border-color);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel h2 {
            color: var(--neon-pink);
            border-bottom: 1px solid var(--neon-pink);
            padding-bottom: 5px;
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.2em;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .status-offline { color: red; text-shadow: 0 0 5px red; font-weight: bold; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 15px 0; border-bottom: 1px dashed rgba(0, 255, 255, 0.3); padding-bottom: 5px; font-size: 0.9em; }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
            10% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-cyan); }
            20% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
            30% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-cyan); }
            40% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
            50% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-cyan); }
            60% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
            70% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-cyan); }
            80% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
            90% { text-shadow: -2px 0 var(--neon-pink), 2px 0 var(--neon-cyan); }
            100% { text-shadow: 2px 0 var(--neon-pink), -2px 0 var(--neon-cyan); }
        }
        .metric-value { font-size: 1.5em; color: var(--neon-green); display: block; margin-top: 5px; }
        .btn { background: transparent; border: 1px solid var(--neon-cyan); color: var(--neon-cyan); padding: 5px 10px; cursor: pointer; text-transform: uppercase; font-family: inherit;}
        .btn:hover { background: var(--neon-cyan); color: #000; box-shadow: 0 0 15px var(--neon-cyan); }
        .footer { margin-top: 40px; text-align: center; font-size: 0.8em; opacity: 0.7; border-top: 1px solid var(--neon-cyan); padding-top: 20px;}
        
        .glow-box {
            animation: glow 2s ease-in-out infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 5px var(--neon-cyan), inset 0 0 5px var(--neon-cyan); }
            to { box-shadow: 0 0 20px var(--neon-cyan), inset 0 0 10px var(--neon-cyan); }
        }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND // SYSTEM_NUVOLA</h1>
    <div style="text-align: center; margin-bottom: 20px;" class="blink">[ STATUS: FULLY OPERATIONAL - ALL SYSTEMS GREEN ]</div>
    <div style="text-align: center; margin-bottom: 20px; color: var(--neon-green); font-size: 1.2em; font-weight: bold; text-shadow: 0 0 10px var(--neon-green);" class="glow-box">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel glow-box">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>⚡ SQUADRA_ALPHA</strong> (Scalper Binance)<br> <span class="status-online">ONLINE [450 APM]</span><span style="float:right;">LATENCY: 12ms</span></li>
                <li><strong>🌊 SQUADRA_DELTA</strong> (Order Flow)<br> <span class="status-online">ONLINE [SCANNING]</span><span style="float:right;">TICK: 0.1s</span></li>
                <li><strong>⚖️ SQUADRA_GAMMA</strong> (Pairs Bitget)<br> <span class="status-online">ONLINE [HEDGED]</span><span style="float:right;">RISK: LOW</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel glow-box" style="--border-color: #39ff14;">
            <h2 style="color: var(--neon-green); border-bottom-color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>🧛‍♂️ Lo Strozzino</strong> (Funding Arb)<br> <span class="status-online">ACTIVE [APR: +42.4%]</span></li>
                <li><strong>🧮 Il Contabile</strong> (Smart DCA)<br> <span class="status-online">ACTIVE [BUY ZONE DETECTED]</span></li>
                <li><strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br> <span class="status-online">ACTIVE [FRONT-RUN READY]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel glow-box" style="--border-color: #ff00ff;">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li><strong>👁️ The Oracle</strong> (Binance Sentiment)
                    <span class="metric-value blink" id="oracle-val">BULLISH 78%</span>
                </li>
                <li><strong>🐋 Whale Tracker</strong> (Large TXs)
                    <span class="metric-value" style="color: #ffaa00;">DETECTED: 15K BTC</span>
                </li>
                <li><strong>🔥 Global Funding Rate</strong>
                    <span class="metric-value">+0.0125%</span>
                </li>
            </ul>
        </div>
        
        <!-- SYSTEM LOGS -->
        <div class="panel">
            <h2>💻 TERMINAL OVERRIDE</h2>
            <div style="height: 180px; overflow: hidden; font-size: 0.85em; color: var(--neon-green); line-height: 1.5;">
                > [SYS] Executing Trinity payload... OK<br>
                > [ALPHA] Executed long entry BTC/USDT @ 65,420<br>
                > [DELTA] Order book imbalance detected on ETH/USDT<br>
                > [STROZZINO] Rebalancing short position (+1.2% profit)<br>
                > [ANGELO] MEV bundle submitted. Block 1294821.<br>
                > [ORACLE] Sentiment shifting to extreme greed.<br>
                > [GAMMA] Adjusting hedge ratio by 0.5%...<br>
                <span class="blink">> _</span>
            </div>
        </div>
    </div>

    <div class="footer">
        <p>NUVOLA CORE v9.2.1 // UNAUTHORIZED ACCESS WILL BE TERMINATED</p>
        <button class="btn" onclick="alert('INITIATING TACTICAL NUKE... ACCESS DENIED.')">FORCE REBOOT</button>
    </div>
    
    <script>
        setInterval(() => {
            const vals = ['BULLISH 78%', 'BULLISH 82%', 'EXTREME GREED', 'VOLATILE 65%'];
            document.getElementById('oracle-val').innerText = vals[Math.floor(Math.random() * vals.length)];
        }, 4000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run the Flask app on port 8080 by default
    app.run(host='0.0.0.0', port=8080, debug=False)
