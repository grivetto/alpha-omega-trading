from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌌</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --bg-color: #050510;
            --panel-bg: rgba(10, 20, 40, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 30px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .panel:hover {
            box-shadow: 0 0 15px var(--neon-blue);
            transform: translateY(-2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        .panel-title {
            color: var(--neon-green);
            border-bottom: 1px solid var(--neon-green);
            padding-bottom: 10px;
            margin-top: 0;
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-on { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-warn { color: #ff0; text-shadow: 0 0 5px #ff0; }
        .status-off { color: #f00; text-shadow: 0 0 5px #f00; }
        
        .item { margin-bottom: 15px; }
        .item-title { font-weight: bold; }
        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(0, 255, 255, 0.3);
            padding: 5px 0;
        }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        .terminal {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            font-size: 0.8em;
            color: #0f0;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>⚡ Orbital Command - Nuvola ⚡</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <div class="item-title">🐺 SQUADRA_ALPHA (Scalper su Binance)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on blink">ONLINE [ACTIVE]</span></div>
                <div class="data-row"><span>Trades/min:</span> <span>142</span></div>
                <div class="data-row"><span>Win Rate:</span> <span>68.4%</span></div>
            </div>
            <div class="item">
                <div class="item-title">🌊 SQUADRA_DELTA (Order Flow)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on">ONLINE [STANDBY]</span></div>
                <div class="data-row"><span>Imbalance:</span> <span class="status-warn">DETECTED (LONG)</span></div>
            </div>
            <div class="item">
                <div class="item-title">⚖️ SQUADRA_GAMMA (Pairs Trading Bitget)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on blink">ONLINE [EXEC]</span></div>
                <div class="data-row"><span>Spread BTC/ETH:</span> <span>+0.45%</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="item">
                <div class="item-title">🕴️ Lo Strozzino (Funding Arb)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on">ONLINE [BACKGROUND]</span></div>
                <div class="data-row"><span>Current APR:</span> <span>14.2%</span></div>
            </div>
            <div class="item">
                <div class="item-title">🧮 Il Contabile (DCA)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on">ONLINE [BACKGROUND]</span></div>
                <div class="data-row"><span>Next Buy:</span> <span>02h 14m</span></div>
            </div>
            <div class="item">
                <div class="item-title">👼 L'Angelo Custode (MEV Arbitrum)</div>
                <div class="data-row"><span>Status:</span> <span class="status-on blink">ONLINE [HUNTING]</span></div>
                <div class="data-row"><span>Mempool:</span> <span>Scanning...</span></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title">👁️ METRICHE DI MERCATO</h2>
            <div class="item">
                <div class="item-title">🔮 The Oracle (Binance Sentiment)</div>
                <div class="data-row"><span>Global Index:</span> <span class="status-on">BULLISH (72/100)</span></div>
                <div class="data-row"><span>Social Volume:</span> <span>+15% (1h)</span></div>
            </div>
            <div class="item">
                <div class="item-title">🐳 Whale Tracker</div>
                <div class="data-row"><span>Last Alert:</span> <span>1,500 BTC moved to Coinbase</span></div>
                <div class="data-row"><span>Severity:</span> <span class="status-warn">HIGH</span></div>
            </div>
            
            <div class="terminal" id="term-log">
                [SYSTEM] Initializing Orbital Command...<br>
                [SYSTEM] All secure protocols engaged.<br>
                [ORACLE] Ingesting Binance order book data...<br>
                [ALPHA] Executing limit order BTC/USDT @ 68,450<br>
                [ANGELO] Flashbot bundle submitted.
            </div>
        </div>
    </div>

    <script>
        const logs = [
            "[ALPHA] Filled 0.5 BTC @ 68,455",
            "[DELTA] Order block detected at 68,000",
            "[STROZZINO] Rebalancing perp positions...",
            "[WHALE] 50,000 ETH transferred from unknown wallet",
            "[SYSTEM] Latency check: 12ms (Tokyo), 8ms (London)",
            "[ORACLE] Sentiment shifting neutral-bearish on LTFs",
            "[GAMMA] Arbitrage opportunity found: +0.22% net"
        ];
        const term = document.getElementById('term-log');
        
        setInterval(() => {
            const newLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toLocaleTimeString('it-IT');
            term.innerHTML += `<br>[${time}] ${newLog}`;
            term.scrollTop = term.scrollHeight;
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
