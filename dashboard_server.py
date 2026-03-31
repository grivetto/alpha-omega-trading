import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-color: #050510;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-pink: #f0f;
            --neon-purple: #b0f;
            --glow-spread: 15px;
        }

        body {
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 255, 0, 0.05) 0%, transparent 60%),
                linear-gradient(0deg, transparent 24%, rgba(0, 255, 0, 0.05) 25%, rgba(0, 255, 0, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 0, 0.05) 75%, rgba(0, 255, 0, 0.05) 76%, transparent 77%, transparent);
            background-size: 100% 100%, 50px 50px;
        }

        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            font-size: 3em;
            margin-bottom: 5px;
            letter-spacing: 5px;
        }

        .subtitle {
            text-align: center;
            color: var(--neon-pink);
            font-size: 1.2em;
            margin-bottom: 40px;
            text-shadow: 0 0 5px var(--neon-pink);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(0, 20, 0, 0.6);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2), 0 0 var(--glow-spread) rgba(0, 255, 0, 0.2);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .panel-red {
            border-color: var(--neon-red);
            color: var(--neon-red);
            box-shadow: inset 0 0 15px rgba(255, 0, 0, 0.2), 0 0 var(--glow-spread) rgba(255, 0, 0, 0.2);
        }
        .panel-red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        .panel-blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.2), 0 0 var(--glow-spread) rgba(0, 255, 255, 0.2);
        }
        .panel-blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }

        .panel-purple {
            border-color: var(--neon-purple);
            color: var(--neon-purple);
            box-shadow: inset 0 0 15px rgba(176, 0, 255, 0.2), 0 0 var(--glow-spread) rgba(176, 0, 255, 0.2);
        }
        .panel-purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        h2 {
            margin-top: 0;
            border-bottom: 1px dashed currentColor;
            padding-bottom: 10px;
            font-size: 1.5em;
            text-transform: uppercase;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
            padding: 5px;
            background: rgba(255, 255, 255, 0.05);
        }

        .status-item span:last-child {
            font-weight: bold;
        }

        .online { color: #0f0; text-shadow: 0 0 5px #0f0; }
        .offline { color: #f00; text-shadow: 0 0 5px #f00; }
        .active { color: #0ff; text-shadow: 0 0 5px #0ff; animation: pulse 2s infinite; }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 6s linear infinite;
        }

        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }

        .glitch {
            animation: glitch 1s linear infinite;
        }

        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
        
        .grid-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .data-cell {
            border: 1px solid rgba(0, 255, 0, 0.3);
            padding: 5px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1>🛰️ ORBITAL COMMAND</h1>
    <div class="subtitle">SYSTEM STATUS: <span class="active">ENGAGED</span> | LOCATION: NUVOLA HQ</div>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.5em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel panel-red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>[A] SQUADRA_ALPHA (Binance Scalp)</span>
                <span class="active">⚡ COMBAT</span>
            </div>
            <div class="status-item">
                <span>[D] SQUADRA_DELTA (Order Flow)</span>
                <span class="active">🎯 TRACKING</span>
            </div>
            <div class="status-item">
                <span>[G] SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="online">🟢 STANDBY</span>
            </div>
            <div style="margin-top: 20px; font-size: 0.8em; opacity: 0.8;">
                > LETHAL FORCE AUTHORIZED.<br>
                > LATENCY: 12ms.
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-purple">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span>💰 Lo Strozzino (Funding Arb)</span>
                <span class="online">🟢 HARVESTING</span>
            </div>
            <div class="status-item">
                <span>🧮 Il Contabile (DCA Grid)</span>
                <span class="online">🟢 ACCUMULATING</span>
            </div>
            <div class="status-item">
                <span>👼 L'Angelo Custode (MEV Arb)</span>
                <span class="active">🛡️ SHIELDING</span>
            </div>
            <div style="margin-top: 20px; font-size: 0.8em; opacity: 0.8;">
                > BACKGROUND PROCESSES STABLE.<br>
                > YIELD GENERATION NOMINAL.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-blue">
            <h2>👁️ THE ORACLE & METRICS</h2>
            <div class="grid-data">
                <div class="data-cell">
                    <div style="font-size: 0.8em; color: #888;">BTC SENTIMENT</div>
                    <div style="font-size: 1.2em; font-weight: bold; color: var(--neon-blue);">BULLISH (82%)</div>
                </div>
                <div class="data-cell">
                    <div style="font-size: 0.8em; color: #888;">WHALE TRACKER</div>
                    <div style="font-size: 1.2em; font-weight: bold; color: var(--neon-red);">ALERT: INFLOW</div>
                </div>
                <div class="data-cell">
                    <div style="font-size: 0.8em; color: #888;">GLOBAL VOLATILITY</div>
                    <div style="font-size: 1.2em; font-weight: bold; color: var(--neon-green);">MED</div>
                </div>
                <div class="data-cell">
                    <div style="font-size: 0.8em; color: #888;">LIQUIDITY POOLS</div>
                    <div style="font-size: 1.2em; font-weight: bold; color: var(--neon-blue);">DEEP</div>
                </div>
            </div>
            <div style="margin-top: 20px; font-size: 0.8em; opacity: 0.8;" class="glitch">
                > SYNCING WITH ON-CHAIN DATA...
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 50px; font-size: 0.8em; opacity: 0.5;">
        NUVOLA SECURE NET | UNAUTHORIZED ACCESS WILL BE TERMINATED
    </div>

    <script>
        // Simple random metric updates for effect
        setInterval(() => {
            const val = document.querySelectorAll('.data-cell div:nth-child(2)')[0];
            const rand = Math.floor(Math.random() * 10) - 5;
            let currentStr = val.innerText;
            if(currentStr.includes('%')) {
               let num = parseInt(currentStr.match(/\d+/)[0]);
               num = Math.max(0, Math.min(100, num + rand));
               val.innerText = currentStr.replace(/\d+/, num);
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
    app.run(host='0.0.0.0', port=5000)
