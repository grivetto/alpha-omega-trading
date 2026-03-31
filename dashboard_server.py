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
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2 {
            color: #0f0;
            text-shadow: 0 0 10px #0f0, 0 0 20px #0f0;
            text-transform: uppercase;
            margin-bottom: 10px;
            border-bottom: 1px solid #0f0;
            padding-bottom: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            border: 1px solid #0f0;
            padding: 15px;
            background: rgba(0, 20, 0, 0.8);
            box-shadow: inset 0 0 10px rgba(0,255,0,0.2), 0 0 15px rgba(0,255,0,0.4);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 0, 0.2), transparent);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .status-online { color: #0f0; text-shadow: 0 0 5px #0f0; }
        .status-active { color: #0ff; text-shadow: 0 0 5px #0ff; }
        .status-warn { color: #ff0; text-shadow: 0 0 5px #ff0; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 8px 0; border-left: 2px solid #0f0; padding-left: 10px; }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        .grid-data {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 5px;
            font-size: 0.9em;
        }
        .grid-data div {
            border: 1px dotted #055;
            padding: 5px;
            text-align: center;
        }
        .metric-up { color: #0f0; }
        .metric-down { color: #f00; }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND <span class="blink">_</span></h1>
    <p>SYSTEM: NUVOLA OS | STATUS: <span class="status-online">ONLINE</span> | UPTIME: 99.99% | ⚙️ PROTOCOLLO TRINITY: <span class="status-online">Online (DCA, Funding, MEV)</span></p>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>SQUADRA_ALPHA</strong> [Scalper @ Binance] <br> Status: <span class="status-active">ENGAGING TARGETS</span> | WinRate: 68.4% 🟢</li>
                <li><strong>SQUADRA_DELTA</strong> [Order Flow @ Deribit] <br> Status: <span class="status-warn">AWAITING VOLATILITY</span> | Flow: Neutral 🟡</li>
                <li><strong>SQUADRA_GAMMA</strong> [Pairs Trading @ Bitget] <br> Status: <span class="status-active">ARBITRAGE ACTIVE</span> | Spread: 0.42% 🔵</li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>Lo Strozzino</strong> [Funding Arb] <br> Status: <span class="status-online">COLLECTING PREMIUMS</span> 💰</li>
                <li><strong>Il Contabile</strong> [DCA Accumulation] <br> Status: <span class="status-online">ACCUMULATING BTC/ETH</span> 📊</li>
                <li><strong>L'Angelo Custode</strong> [MEV @ Arbitrum] <br> Status: <span class="status-online">MEMPOOL SNIPING</span> ⚡</li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📡 THE ORACLE & WHALE TRACKER</h2>
            <div class="grid-data" id="market-data">
                <div>SYM</div><div>PRICE</div><div>SENTIMENT</div><div>FLOW</div>
                <div>BTC/USDT</div><div class="metric-up">68,420.50</div><div class="metric-up">BULLISH</div><div class="metric-up">+450M</div>
                <div>ETH/USDT</div><div class="metric-down">3,520.10</div><div class="status-warn">NEUTRAL</div><div class="metric-down">-12M</div>
                <div>SOL/USDT</div><div class="metric-up">185.30</div><div class="metric-up">HYPER</div><div class="metric-up">+85M</div>
                <div>ARB/USDT</div><div class="metric-up">1.45</div><div class="metric-up">BULLISH</div><div class="metric-up">+5M</div>
            </div>
        </div>
    </div>
    
    <script>
        // Fake real-time updates for cyberpunk effect
        setInterval(() => {
            const prices = document.querySelectorAll('.grid-data div:nth-child(4n+2)');
            for(let i=1; i<prices.length; i++) {
                let current = parseFloat(prices[i].innerText.replace(/,/g, ''));
                let change = current * (Math.random() * 0.002 - 0.001);
                prices[i].innerText = (current + change).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                if(change > 0) { prices[i].className = 'metric-up'; } else { prices[i].className = 'metric-down'; }
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
