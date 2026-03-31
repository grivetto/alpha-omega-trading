from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --neon-yellow: #fffb00;
            --panel-bg: rgba(0, 20, 40, 0.6);
            --border-color: rgba(0, 243, 255, 0.3);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 243, 255, 0.05) 25%, rgba(0, 243, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, 0.05) 75%, rgba(0, 243, 255, 0.05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 243, 255, 0.05) 25%, rgba(0, 243, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, 0.05) 75%, rgba(0, 243, 255, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 { text-shadow: 0 0 10px var(--neon-blue); text-transform: uppercase; letter-spacing: 2px; }
        .header { text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 20px; margin-bottom: 30px; animation: flicker 2s infinite alternate; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 20px; border-radius: 5px; box-shadow: 0 0 15px rgba(0, 243, 255, 0.1); position: relative; overflow: hidden; }
        .panel::before { content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(to right, transparent, rgba(0, 243, 255, 0.1), transparent); animation: scan 4s infinite linear; }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 1.5s infinite; }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .status-standby { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .metric { display: flex; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid rgba(0,243,255,0.2); padding-bottom: 5px; }
        @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; text-shadow: 0 0 15px var(--neon-green); } 100% { opacity: 0.8; } }
        @keyframes scan { 0% { left: -100%; } 100% { left: 200%; } }
        @keyframes flicker { 0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; } 20%, 24%, 55% { opacity: 0.5; } }
        .data-stream { font-size: 0.8em; opacity: 0.7; height: 100px; overflow: hidden; display: flex; flex-direction: column-reverse; }
        .btn { background: transparent; color: var(--neon-red); border: 1px solid var(--neon-red); padding: 5px 10px; cursor: pointer; text-shadow: 0 0 5px var(--neon-red); box-shadow: 0 0 5px rgba(255, 7, 58, 0.3); font-family: inherit; }
        .btn:hover { background: var(--neon-red); color: black; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 NUVOLA // ORBITAL COMMAND 🌐</h1>
        <p>QUANTITATIVE OPERATIONS CENTER - UPLINK ESTABLISHED</p>
        <p>STATUS: <span class="status-online">DEFCON 5 - NOMINAL</span> | TIME: <span id="clock"></span></p>
        <p>⚙️ PROTOCOLLO TRINITY: <span class="status-online">Online (DCA, Funding, MEV)</span></p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric">
                <span>🐺 SQUADRA_ALPHA (Scalper @ Binance)</span>
                <span class="status-active">ENGAGING [145.2 t/s]</span>
            </div>
            <div class="metric">
                <span>🦅 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-active">MONITORING [L2 Sync]</span>
            </div>
            <div class="metric">
                <span>🐍 SQUADRA_GAMMA (Pairs Trading @ Bitget)</span>
                <span class="status-active">HEDGED [Spread: 0.4%]</span>
            </div>
            <div style="margin-top: 15px; border-top: 1px dashed var(--neon-blue); padding-top: 10px;">
                <span style="font-size: 0.8em;">LIVE EXECUTION FEED:</span>
                <div class="data-stream" id="hft-feed"></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="metric">
                <span>🎩 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">ONLINE [Yield: 14.2% APY]</span>
            </div>
            <div class="metric">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">ONLINE [Next Buy: 4h 12m]</span>
            </div>
            <div class="metric">
                <span>🛡️ L'Angelo Custode (MEV @ Arbitrum)</span>
                <span class="status-online">ONLINE [Scanning Mempool]</span>
            </div>
            <div style="margin-top: 15px;">
                <button class="btn">KILLSWITCH / TRINITY</button>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📡 METRICHE DI MERCATO & INTEL</h2>
            <div style="display: flex; gap: 20px;">
                <div style="flex: 1;">
                    <h3>👁️ THE ORACLE (Sentiment)</h3>
                    <div class="metric"><span>BTC/USDT Fear & Greed</span> <span style="color: var(--neon-green)">65 (GREED)</span></div>
                    <div class="metric"><span>Binance Long/Short Ratio</span> <span style="color: var(--neon-pink)">1.42</span></div>
                    <div class="metric"><span>Global Liquidations (24h)</span> <span style="color: var(--neon-red)">$ 142.5M</span></div>
                </div>
                <div style="flex: 1;">
                    <h3>🐋 WHALE TRACKER</h3>
                    <div class="metric"><span>Alert #8921</span> <span>1,200 BTC moved to Coinbase</span></div>
                    <div class="metric"><span>Alert #8920</span> <span>50,000 ETH withdrawn from Binance</span></div>
                    <div class="metric"><span>Alert #8919</span> <span>Suspicious stablecoin mint: $500M USDT</span></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Clock
        setInterval(() => { document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').substr(0, 19) + ' UTC'; }, 1000);

        // HFT Feed Simulator
        const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT'];
        const actions = ['BUY', 'SELL'];
        const feed = document.getElementById('hft-feed');
        setInterval(() => {
            const pair = pairs[Math.floor(Math.random() * pairs.length)];
            const action = actions[Math.floor(Math.random() * actions.length)];
            const amount = (Math.random() * 10).toFixed(4);
            const price = (Math.random() * 50000).toFixed(2);
            const color = action === 'BUY' ? 'var(--neon-green)' : 'var(--neon-red)';
            const el = document.createElement('div');
            el.innerHTML = `> [${new Date().toISOString().substr(11,8)}] <span style="color:${color}">${action}</span> ${amount} ${pair} @ ${price}`;
            feed.prepend(el);
            if (feed.children.length > 5) feed.removeChild(feed.lastChild);
        }, 800);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
