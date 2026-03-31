from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-magenta: #f0f;
            --neon-cyan: #0ff;
            --neon-red: #f00;
            --neon-yellow: #ff0;
            --bg-dark: #050505;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-shadow: 0 0 5px var(--neon-green);
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid var(--neon-magenta);
            box-shadow: 0 0 10px var(--neon-magenta) inset, 0 0 15px var(--neon-magenta);
            padding: 20px;
            border-radius: 8px;
            background: rgba(255, 0, 255, 0.05);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            pointer-events: none;
        }
        .panel h2 {
            color: var(--neon-magenta);
            text-shadow: 0 0 8px var(--neon-magenta);
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 10px;
            font-size: 1.2em;
        }
        .squad {
            border-left: 3px solid var(--neon-green);
            padding-left: 15px;
            margin-bottom: 15px;
            background: rgba(0, 255, 0, 0.05);
            padding-top: 5px;
            padding-bottom: 5px;
        }
        .squad.alpha { border-color: var(--neon-red); color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); background: rgba(255, 0, 0, 0.05); }
        .squad.delta { border-color: var(--neon-yellow); color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); background: rgba(255, 255, 0, 0.05); }
        .squad.gamma { border-color: var(--neon-cyan); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); background: rgba(0, 255, 255, 0.05); }
        
        .status {
            float: right;
            animation: pulse 1.5s infinite;
            font-weight: bold;
        }
        .online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        
        .scanline {
            width: 100%;
            height: 150px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(0,255,255,0.1) 50%, rgba(255,255,255,0));
            animation: scan 8s linear infinite;
        }
        @keyframes scan {
            0% { top: -150px; }
            100% { top: 100%; }
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid var(--neon-green); padding: 8px; text-align: left; }
        th { background: rgba(0, 255, 0, 0.15); color: #fff; text-shadow: 0 0 5px #fff; }
        tr:hover { background: rgba(0, 255, 0, 0.1); }
        
        .list-unstyled { list-style-type: none; padding-left: 0; }
        .list-unstyled li { margin-bottom: 8px; border-bottom: 1px solid rgba(0, 255, 0, 0.2); padding-bottom: 4px; }
        .list-unstyled li:last-child { border-bottom: none; }
        
        .glitch {
            animation: glitch 1s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1><span class="glitch">🛰️ NUVOLA ORBITAL COMMAND</span></h1>
    
    <div class="grid">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="squad alpha">
                <strong>SQUADRA_ALPHA</strong> [Scalper @ Binance] <span class="status online">ONLINE 🟢</span><br>
                <small>Latency: 11ms | Executed: 18,402 trades | PnL: +1.24%</small>
            </div>
            <div class="squad delta">
                <strong>SQUADRA_DELTA</strong> [Order Flow @ Bybit] <span class="status online">ONLINE 🟢</span><br>
                <small>Imbalance: Bearish | Positions: 3 Short | Leverage: 5x</small>
            </div>
            <div class="squad gamma">
                <strong>SQUADRA_GAMMA</strong> [Pairs Trading @ Bitget] <span class="status online">ONLINE 🟢</span><br>
                <small>Spread: 0.42% | Cointegration: 98.5% | Active Pairs: 12</small>
            </div>
        </div>

        <!-- TRINITY PROTOCOL -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; font-size: 1.1em; color: var(--neon-green); margin-bottom: 15px; text-shadow: 0 0 5px var(--neon-green);">
                <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
            </div>
            <div class="squad">
                <strong>Lo Strozzino</strong> (Funding Arb) <span class="status online">ACTIVE 💸</span><br>
                <small>Current Yield: 18.4% APR | Hedged: 100% | Exposure: $45k</small>
            </div>
            <div class="squad">
                <strong>Il Contabile</strong> (DCA) <span class="status online">ACTIVE 🏦</span><br>
                <small>Next Buy: 02h 14m | Target: BTC, ETH | Status: Accumulating</small>
            </div>
            <div class="squad">
                <strong>L'Angelo Custode</strong> (MEV Arbitrum) <span class="status online">ACTIVE 👼</span><br>
                <small>Mempool: 45 tx/s | Sandwiches: 0 | Snipes: 3 (Today)</small>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>🔮 THE ORACLE (Binance Sentiment)</h2>
            <table>
                <tr><th>Asset</th><th>Signal</th><th>Confidence</th></tr>
                <tr><td>BTC/USDT</td><td>STRONG BUY 🟢</td><td>92%</td></tr>
                <tr><td>ETH/USDT</td><td>NEUTRAL 🟡</td><td>51%</td></tr>
                <tr><td>SOL/USDT</td><td>SELL 🔴</td><td>78%</td></tr>
                <tr><td>DOGE/USDT</td><td>VOLATILE 🟣</td><td>--%</td></tr>
            </table>
        </div>

        <!-- WHALE TRACKER -->
        <div class="panel">
            <h2>🐋 WHALE TRACKER</h2>
            <ul class="list-unstyled">
                <li>🚨 <strong>JUST NOW</strong> - 1,200 BTC moved to Binance (Possible Dump)</li>
                <li>🔥 <strong>-15m</strong> - 15,000 ETH withdrawn from Coinbase (Cold Storage)</li>
                <li>⚠️ <strong>-42m</strong> - $50M Short opened on Bitfinex</li>
                <li>💎 <strong>-1h 10m</strong> - 2,500,000 USDT minted at Tether Treasury</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start on port 5000, visible to all interfaces if needed
    app.run(host='0.0.0.0', port=5000)
