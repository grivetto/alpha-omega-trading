import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --bg-dark: #0a0a0c;
            --panel-bg: rgba(10, 20, 30, 0.85);
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
            text-shadow: 0 0 10px currentColor;
            margin-bottom: 10px;
        }
        h1 { color: var(--neon-blue); text-align: center; font-size: 2.5em; letter-spacing: 5px; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px;}
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2) inset;
            padding: 20px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-indicator {
            display: inline-block; width: 10px; height: 10px; border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: blink 1.5s infinite alternate;
        }
        .status-offline { background-color: red; box-shadow: 0 0 10px red; }
        .status-warning { background-color: yellow; box-shadow: 0 0 10px yellow; }
        @keyframes blink { 0% { opacity: 0.5; } 100% { opacity: 1; } }
        
        .assault-team { color: var(--neon-pink); border-color: var(--neon-pink); box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) inset; }
        .assault-team h2 { color: var(--neon-pink); }
        .assault-team .panel::before { background: linear-gradient(90deg, transparent, var(--neon-pink), transparent); }

        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(255,255,255,0.2); padding-bottom: 5px; display: flex; justify-content: space-between;}
        
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { background: rgba(0,0,0,0.5); border: 1px solid var(--neon-green); padding: 10px; text-align: center; }
        .metric-value { font-size: 1.5em; font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        
        .glitch { animation: glitch 1s linear infinite; }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>

    <h1 class="glitch">🛰️ ORBITAL COMMAND NEURAL LINK</h1>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel assault-team">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 SQUADRA_ALPHA (Binance Scalp)</span> <span class="status-indicator"></span></li>
                <li><span>🦅 SQUADRA_DELTA (Order Flow)</span> <span class="status-indicator"></span></li>
                <li><span>🐍 SQUADRA_GAMMA (Bitget Pairs)</span> <span class="status-indicator status-warning"></span></li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">> EXEC_MODE: AGGRESSIVE<br>> LATENCY: 12ms</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="color: var(--neon-green); font-weight: bold; margin-bottom: 15px; border: 1px dashed var(--neon-green); padding: 5px; text-align: center;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <ul>
                <li><span>🦇 Lo Strozzino (Funding Arb)</span> <span class="status-indicator"></span></li>
                <li><span>🧮 Il Contabile (DCA Engine)</span> <span class="status-indicator"></span></li>
                <li><span>👼 L'Angelo Custode (MEV Arbitrum)</span> <span class="status-indicator"></span></li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">> BACKGROUND_DAEMONS: ONLINE<br>> RISK_LEVEL: MODERATE</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ THE ORACLE & METRICS</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>BTC SENTIMENT</div>
                    <div class="metric-value" style="color: var(--neon-green)">BULL [88%]</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER</div>
                    <div class="metric-value" style="color: var(--neon-pink)">ALERT</div>
                </div>
                <div class="metric-box">
                    <div>GLOBAL LIQUIDITY</div>
                    <div class="metric-value" style="color: var(--neon-blue)">$2.4T</div>
                </div>
                <div class="metric-box">
                    <div>ORBITAL UPTIME</div>
                    <div class="metric-value">99.9%</div>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">> FEED: SECURE LINK ESTABLISHED</div>
        </div>
    </div>

    <script>
        setInterval(() => {
            const el = document.querySelector('.assault-team div');
            if(el) {
               el.innerHTML = '> EXEC_MODE: AGGRESSIVE<br>> LATENCY: ' + (Math.floor(Math.random() * 10) + 8) + 'ms';
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)