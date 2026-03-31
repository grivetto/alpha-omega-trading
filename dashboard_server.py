from flask import Flask, render_template_string
import os

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
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --bg-color: #050505;
            --panel-bg: rgba(0, 20, 0, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            margin-top: 0;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            animation: flicker 3s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2), inset 0 0 10px rgba(0, 255, 0, 0.1);
            padding: 20px;
            border-radius: 4px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
        }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.blue h2 { text-shadow: 0 0 8px var(--neon-blue); border-bottom: 1px solid var(--neon-blue); }
        
        .panel.pink {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2), inset 0 0 10px rgba(255, 0, 255, 0.1);
        }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.pink h2 { text-shadow: 0 0 8px var(--neon-pink); border-bottom: 1px solid var(--neon-pink); }

        .panel h2 {
            border-bottom: 1px solid var(--neon-green);
            padding-bottom: 10px;
            text-shadow: 0 0 8px var(--neon-green);
            font-size: 1.2rem;
        }
        .item {
            margin-bottom: 20px;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border: 1px dashed rgba(255,255,255,0.2);
        }
        .status {
            float: right;
            font-weight: bold;
            animation: blink 1.5s infinite;
            text-shadow: 0 0 5px currentColor;
        }
        .status.online { color: var(--neon-green); }
        .status.active { color: var(--neon-blue); }
        .status.hunting { color: var(--neon-pink); }
        
        .bar-bg {
            background: #111;
            height: 6px;
            width: 100%;
            margin-top: 8px;
            border: 1px solid #333;
        }
        .bar-fill {
            height: 100%;
            background: var(--neon-green);
            width: 0%;
            box-shadow: 0 0 8px var(--neon-green);
            transition: width 0.5s ease-in-out;
        }
        .blue .bar-fill { background: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); }
        .pink .bar-fill { background: var(--neon-pink); box-shadow: 0 0 8px var(--neon-pink); }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.5; text-shadow: none; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            animation: scanline 8s linear infinite;
            top: -100px;
            left: 0;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
        .console-text {
            font-size: 0.85em;
            opacity: 0.8;
            margin-top: 5px;
            display: block;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>/// NUVOLA TACTICAL OVERVIEW | CLASSIFIED QUANTITATIVE HUB ///</p>
        <div style="color: var(--neon-blue); font-weight: bold; margin-top: 10px; font-size: 1.2em; text-shadow: 0 0 10px var(--neon-blue); border: 1px dashed var(--neon-blue); display: inline-block; padding: 10px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <strong>[ 🐺 SQUADRA_ALPHA ]</strong> <span class="status online">ONLINE</span>
                <br><small>Target: Binance Scalping | Latency: 12ms | Win Rate: 68%</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 87%;"></div></div>
            </div>
            <div class="item">
                <strong>[ 🦅 SQUADRA_DELTA ]</strong> <span class="status active">ACTIVE</span>
                <br><small>Target: Order Flow Spoofing | Volume: $4.2M 24h</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 65%;"></div></div>
            </div>
            <div class="item">
                <strong>[ 🦂 SQUADRA_GAMMA ]</strong> <span class="status hunting">HUNTING</span>
                <br><small>Target: Bitget Pairs Trading | Spread: 0.15%</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 42%;"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>⚕️ PROTOCOLLO TRINITY</h2>
            <div class="item">
                <strong>[ 🦇 Lo Strozzino ]</strong> <span class="status active">EXTRACTING</span>
                <br><small>Mode: Funding Arbitrage | APY: 18.4%</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 92%;"></div></div>
            </div>
            <div class="item">
                <strong>[ 🧮 Il Contabile ]</strong> <span class="status online">STABLE</span>
                <br><small>Mode: Dynamic DCA | Reserves: Optimal</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 98%;"></div></div>
            </div>
            <div class="item">
                <strong>[ 👼 L'Angelo Custode ]</strong> <span class="status hunting">MONITORING</span>
                <br><small>Mode: Arbitrum MEV / Snipe | Mempool: Clear</small>
                <div class="bar-bg"><div class="bar-fill" style="width: 25%;"></div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="item">
                <strong>[ 👁️ The Oracle ]</strong> <span class="status online">SYNCED</span>
                <br><small>Binance Sentiment: <span style="color:#0f0; text-shadow:0 0 5px #0f0;">BULLISH (78%)</span></small>
                <span class="console-text">> NLP processing 45k tweets/sec...<br>> Orderbook imbalance detected.</span>
            </div>
            <div class="item">
                <strong>[ 🐳 Whale Tracker ]</strong> <span class="status active">PINGING</span>
                <br><small>Recent: 15,000 ETH moved to Coinbase</small>
                <span class="console-text">> Alert Level: <span style="color:#ff0">DEFCON 3</span><br>> Tracking 142 known entities.</span>
            </div>
            <div class="item">
                <strong>[ ⚡ System Load ]</strong> <span class="status online">NOMINAL</span>
                <br><small>CPU: 14% | RAM: 32% | NET: 1.2 GB/s</small>
                <span class="console-text">> Core temps normal.<br>> Encrypted tunnel stable.</span>
            </div>
        </div>
    </div>
    
    <script>
        // Randomize bars for effect
        setInterval(() => {
            document.querySelectorAll('.bar-fill').forEach(bar => {
                let current = parseFloat(bar.style.width) || 50;
                let jitter = (Math.random() - 0.5) * 15;
                let next = Math.max(10, Math.min(100, current + jitter));
                bar.style.width = next + '%';
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
    # Usa la porta 5000 di default
    app.run(host='0.0.0.0', port=5000)
