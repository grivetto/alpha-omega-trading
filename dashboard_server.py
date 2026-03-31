import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ☁️ ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #00ff41;
            --neon-cyan: #0ff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff003c;
            --panel-bg: rgba(10, 20, 30, 0.8);
            --border: 1px solid rgba(0, 255, 65, 0.3);
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }

        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            letter-spacing: 5px;
            text-transform: uppercase;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 30px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: var(--border);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 65, 0.1);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .panel-title {
            font-size: 1.2em;
            font-weight: bold;
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 10px;
        }

        .status {
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 5px;
            background: rgba(0, 255, 65, 0.05);
            border-left: 3px solid var(--neon-green);
        }
        
        .status.cyan { border-left-color: var(--neon-cyan); color: var(--neon-cyan); background: rgba(0, 255, 255, 0.05); }
        .status.red { border-left-color: var(--neon-red); color: var(--neon-red); background: rgba(255, 0, 60, 0.05); }

        .blink {
            animation: blink-animation 1.5s steps(2, start) infinite;
        }

        @keyframes blink-animation {
            to { visibility: hidden; }
        }

        .grid-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.85em;
        }

        .data-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 255, 255, 0.2);
            padding: 10px;
            text-align: center;
        }

        .data-value {
            font-size: 1.5em;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            margin-top: 5px;
        }

        .glitch-text {
            color: var(--neon-red);
            text-shadow: 2px 0 var(--neon-cyan), -2px 0 var(--neon-magenta);
            animation: glitch 2s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--neon-cyan), -2px 0 var(--neon-magenta); }
            20% { text-shadow: -2px 0 var(--neon-cyan), 2px 0 var(--neon-magenta); }
            40% { text-shadow: 2px 0 var(--neon-cyan), -2px 0 var(--neon-magenta); }
            60% { text-shadow: -2px 0 var(--neon-cyan), 2px 0 var(--neon-magenta); }
            80% { text-shadow: 2px 0 var(--neon-cyan), -2px 0 var(--neon-magenta); }
            100% { text-shadow: -2px 0 var(--neon-cyan), 2px 0 var(--neon-magenta); }
        }

    </style>
</head>
<body>

    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>

    <div style="text-align:center; padding: 10px; margin-bottom: 20px; background: rgba(0,255,65,0.1); border: 1px solid var(--neon-green); border-radius: 5px; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">
        <span class="blink" style="margin-right: 10px;">🟢</span> <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong> <span class="blink" style="margin-left: 10px;">🟢</span>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <div class="status">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="blink">[ ACTIVE ]</span>
            </div>
            <div class="status cyan">
                <span>🦅 SQUADRA_DELTA (Order Flow)</span>
                <span class="blink" style="animation-delay: 0.3s">[ ACTIVE ]</span>
            </div>
            <div class="status">
                <span>🐍 SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="blink" style="animation-delay: 0.6s">[ ACTIVE ]</span>
            </div>
            <div class="grid-data" style="margin-top: 15px;">
                <div class="data-box">
                    <div>ALPHA PNL (24H)</div>
                    <div class="data-value">+4.2%</div>
                </div>
                <div class="data-box">
                    <div>WIN RATE</div>
                    <div class="data-value" style="color:var(--neon-green)">68.5%</div>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-title">⚙️ PROTOCOLLO TRINITY</div>
            <div class="status cyan">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span>[ ONLINE 🟢 ]</span>
            </div>
            <div class="status">
                <span>🧮 Il Contabile (DCA)</span>
                <span>[ ONLINE 🟢 ]</span>
            </div>
            <div class="status red">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span>[ SHADOW 🟣 ]</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: rgba(255,255,255,0.6); padding: 10px; background: rgba(0,0,0,0.5); border: 1px dashed rgba(255,0,255,0.5);">
                <span class="blink">>></span> Background daemons running gracefully. Risk modules fully operational. Max Drawdown limit locked at 3.0%.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-title">📊 METRICHE DI MERCATO</div>
            <div class="status">
                <span>🔮 The Oracle (Binance Sentiment)</span>
                <span style="color:var(--neon-green)">BULLISH (78%)</span>
            </div>
            <div class="status cyan">
                <span>🐳 Whale Tracker</span>
                <span>SCANNING...</span>
            </div>
            <div class="grid-data" style="margin-top: 15px;">
                <div class="data-box">
                    <div>BTC/USDT SPREAD</div>
                    <div class="data-value" style="font-size:1.2em" id="spread-value">0.01$</div>
                </div>
                <div class="data-box">
                    <div>LIQUIDATIONS (1H)</div>
                    <div class="data-value glitch-text" style="font-size:1.2em; color:var(--neon-red)">$14.2M</div>
                </div>
                <div class="data-box" style="grid-column: span 2;">
                    <div>SYSTEM LOAD (NUVOLA)</div>
                    <div class="data-value" style="font-size:1em; display:flex; align-items:center; justify-content:center; gap:10px;">
                        [||||||||||------] 64%
                    </div>
                </div>
            </div>
        </div>

    </div>

    <script>
        setInterval(() => {
            const spread = (Math.random() * 0.05).toFixed(2);
            document.getElementById('spread-value').innerText = spread + '$';
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Try multiple common ports to ensure it binds successfully
    import socket
    def get_open_port(start_port):
        for port in range(start_port, start_port+10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port
        return start_port
        
    port = get_open_port(5000)
    app.run(host='0.0.0.0', port=port, debug=False)
