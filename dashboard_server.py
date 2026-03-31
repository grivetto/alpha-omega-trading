from flask import Flask, render_template_string

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
            --neon-green: #39ff14;
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.85);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                linear-gradient(rgba(57, 255, 20, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(57, 255, 20, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            margin-top: 0;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 15px;
            margin-bottom: 30px;
            animation: flicker 4s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15), inset 0 0 15px rgba(57, 255, 20, 0.05);
            position: relative;
            backdrop-filter: blur(2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }
        .panel.trinity {
            border-color: var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.15), inset 0 0 15px rgba(0, 255, 255, 0.05);
        }
        .panel.trinity::before {
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        .panel.metrics {
            border-color: var(--neon-pink);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.15), inset 0 0 15px rgba(255, 0, 255, 0.05);
        }
        .panel.metrics::before {
            background: var(--neon-pink);
            box-shadow: 0 0 15px var(--neon-pink);
        }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); font-weight: bold; }
        .status-warning { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); font-weight: bold; animation: blink 1.5s infinite; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 12px; border-bottom: 1px dashed rgba(57,255,20,0.3); padding-bottom: 8px; line-height: 1.4; }
        li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: 1; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.7; }
        }
        .scanline {
            width: 100%;
            height: 150px;
            z-index: 999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.6;
            animation: scan 8s linear infinite;
        }
        @keyframes scan {
            0% { top: -150px; }
            100% { top: 100vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA BASE</h1>
        <p>SYSTEM STATUS: <span class="status-online">[ ONLINE ]</span> &nbsp;|&nbsp; UPTIME: 99.99% &nbsp;|&nbsp; QUANTUM ENCRYPTION: SECURE</p>
        <h3 style="color: var(--neon-blue); text-shadow: 0 0 15px var(--neon-blue); margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>SQUADRA_ALPHA</strong> 🦇 [Scalper // Binance]<br>
                    Status: <span class="status-active">ENGAGED</span> | Ping: 8ms | Latency: Ultra-Low<br>
                    > Executing micro-trades... PnL: +$342.10
                </li>
                <li><strong>SQUADRA_DELTA</strong> 🦅 [Order Flow // Deribit]<br>
                    Status: <span class="status-active">SCANNING</span> | Book Imbalance: 72% BUY<br>
                    > Tracking institutional footprint...
                </li>
                <li><strong>SQUADRA_GAMMA</strong> 🐺 [Pairs Trading // Bitget]<br>
                    Status: <span class="status-online">STANDBY</span> | Z-Score: 1.85<br>
                    > Awaiting convergence threshold (2.0)...
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>Lo Strozzino</strong> 🎩 [Funding Arb]<br>
                    Status: <span class="status-active">ARBITRAGING</span> | Spread: 0.05%<br>
                    > Rebalancing perpetual swaps silently...
                </li>
                <li><strong>Il Contabile</strong> 🧮 [DCA Accumulation]<br>
                    Status: <span class="status-online">ACCUMULATING</span> | Next Buy: 04m 12s<br>
                    > Cold storage transfer pending...
                </li>
                <li><strong>L'Angelo Custode</strong> 🛡️ [MEV // Arbitrum]<br>
                    Status: <span class="status-warning">HUNTING</span> | Mempool: 520 tx/s<br>
                    > Sniping sandwich opportunities...
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">📊 MARKET METRICS (LIVE)</h2>
            <ul>
                <li><strong>The Oracle</strong> 🔮 [Binance Sentiment]<br>
                    Index: <span style="color: yellow; text-shadow: 0 0 5px yellow;">78 (EXTREME GREED)</span><br>
                    > Retail FOMO detected. Adjusting risk parameters.
                </li>
                <li><strong>Whale Tracker</strong> 🐋 [On-Chain Alerts]<br>
                    Last Alert: 1,200 BTC moved to Coinbase Pro (4 mins ago)<br>
                    > Preparing for potential dump.
                </li>
                <li><strong>Liquidity Matrix</strong> 💧<br>
                    Total Value Locked: $24,580,900.00<br>
                    > Stablecoin reserves nominal.
                </li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
