from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-red: #ff003c;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(0deg, transparent 24%, rgba(57, 255, 20, .05) 25%, rgba(57, 255, 20, .05) 26%, transparent 27%, transparent 74%, rgba(57, 255, 20, .05) 75%, rgba(57, 255, 20, .05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(57, 255, 20, .05) 25%, rgba(57, 255, 20, .05) 26%, transparent 27%, transparent 74%, rgba(57, 255, 20, .05) 75%, rgba(57, 255, 20, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 5px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 10px rgba(57, 255, 20, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(57, 255, 20, 0.1), transparent);
            animation: scan 4s linear infinite;
        }
        @keyframes scan {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .panel-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status {
            margin-left: auto;
            color: var(--neon-cyan);
            animation: blink 2s infinite;
            font-size: 0.8em;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .item {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            border-left: 2px solid var(--neon-green);
            padding-left: 10px;
            background: rgba(0,0,0,0.5);
            padding: 8px 10px;
            align-items: center;
        }
        .value-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .value-down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; }
        
        .terminal {
            font-size: 0.9em;
            color: #aaa;
            height: 120px;
            overflow-y: hidden;
            background: #000;
            padding: 10px;
            border: 1px solid #333;
            margin-top: 15px;
            font-family: monospace;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.8);
        }
        .terminal p { margin: 4px 0; }
    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div style="text-align: center; color: var(--neon-green); margin-bottom: 20px; font-size: 1.1em;">
        > SYSTEM STATUS: <span style="color: var(--neon-cyan); font-weight: bold; text-shadow: 0 0 5px var(--neon-cyan);">ONLINE</span> | SECURE CONNECTION ESTABLISHED<br>
        <span style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT) <span class="status">ACTIVE DEPLOYMENT</span></div>
            <div class="item">
                <span>🐺 SQUADRA_ALPHA <br><small style="color: #666;">Scalper [Binance]</small></span>
                <span class="value-up">Deploying / Hunting</span>
            </div>
            <div class="item">
                <span>⚡ SQUADRA_DELTA <br><small style="color: #666;">Order Flow [Bybit]</small></span>
                <span class="value-up">Tracking Liquidity</span>
            </div>
            <div class="item">
                <span>⚖️ SQUADRA_GAMMA <br><small style="color: #666;">Pairs Trading [Bitget]</small></span>
                <span class="value-up">Synced / Arbitrage</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);">
            <div class="panel-title" style="border-color: var(--neon-cyan); color: var(--neon-cyan);">
                🔮 PROTOCOLLO TRINITY <span class="status" style="color: var(--neon-green);">BACKGROUND SERVICES ONLINE</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-cyan);">
                <span>🕴️ Lo Strozzino <br><small style="color: #666;">Funding Arb</small></span>
                <span class="value-up">Monitoring Yields</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-cyan);">
                <span>🧮 Il Contabile <br><small style="color: #666;">DCA Matrix</small></span>
                <span class="value-up">Accumulating Alpha</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-cyan);">
                <span>👼 L'Angelo Custode <br><small style="color: #666;">MEV [Arbitrum]</small></span>
                <span class="value-up">Guarding Mempool</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 60, 0.2);">
            <div class="panel-title" style="border-color: var(--neon-red); color: var(--neon-red);">
                📊 METRICHE DI MERCATO <span class="status" style="color: var(--neon-red);">LIVE FEED</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-red);">
                <span>👁️ The Oracle <br><small style="color: #666;">Binance Sentiment</small></span>
                <span class="value-up" style="color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">BULLISH 72%</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-red);">
                <span>🐋 Whale Tracker <br><small style="color: #666;">Large TXs</small></span>
                <span class="value-down">HIGH ALERT</span>
            </div>
            <div class="item" style="border-left-color: var(--neon-red);">
                <span>🔥 Nuvola Volatility Index <br><small style="color: #666;">Market Entropy</small></span>
                <span class="value-up">ELEVATED</span>
            </div>
        </div>
    </div>

    <div class="panel" style="margin-top: 20px;">
        <div class="panel-title">📡 COMM LINK / LOGS</div>
        <div class="terminal" id="terminal">
            <p>> Initializing Orbital Command...</p>
            <p>> Loading Trinity Modules...</p>
            <p>> Establishing secure WebSocket to Binance...</p>
            <p>> SQUADRA_ALPHA reporting readiness.</p>
        </div>
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const messages = [
            "> Detecting liquidity pocket on ETH/USDT...",
            "> L'Angelo Custode intercepted sandwich attack. Funds secure.",
            "> Il Contabile executing micro-buy on BTC support level.",
            "> Whale Tracker alert: 5000 BTC moved to Binance cold wallet.",
            "> SQUADRA_DELTA recalibrating order flow matrix...",
            "> The Oracle predicts short squeeze in 4 hours.",
            "> Lo Strozzino collecting 0.01% funding rate.",
            "> SQUADRA_GAMMA identified 0.15% spread anomaly.",
            "> Optimizing HFT connection latency... PING: 4ms"
        ];

        setInterval(() => {
            const p = document.createElement('p');
            const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false });
            p.innerHTML = `<span style="color: var(--neon-cyan)">[${timeStr}]</span> ${messages[Math.floor(Math.random() * messages.length)]}`;
            terminal.appendChild(p);
            terminal.scrollTop = terminal.scrollHeight;
            if(terminal.children.length > 25) {
                terminal.removeChild(terminal.firstChild);
            }
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Flask app will run on port 5000 by default
    app.run(host='0.0.0.0', port=5000, debug=False)
