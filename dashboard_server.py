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
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 15, 0.85);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
            position: relative;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 4px 15px rgba(0, 243, 255, 0.3);
            margin-bottom: 30px;
            animation: pulse 3s infinite;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 10;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.1) inset, 0 0 15px rgba(0, 243, 255, 0.15);
            transition: all 0.3s ease;
            backdrop-filter: blur(5px);
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.4) inset, 0 0 30px rgba(0, 243, 255, 0.4);
            border-color: var(--neon-pink);
            transform: translateY(-2px);
        }
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 12px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            font-size: 1.4rem;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            font-weight: bold;
            animation: blink 2s infinite;
        }
        .status-warning {
            color: #ffb300;
            text-shadow: 0 0 10px #ffb300;
            font-weight: bold;
        }
        .item {
            margin: 15px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid var(--neon-blue);
            border-radius: 4px;
            transition: all 0.2s ease;
        }
        .item:hover {
            background: rgba(0, 243, 255, 0.05);
            border-left-color: var(--neon-pink);
        }
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9rem;
        }
        .metrics-table th, .metrics-table td {
            border: 1px solid rgba(0, 243, 255, 0.2);
            padding: 10px;
            text-align: left;
        }
        .metrics-table th {
            color: var(--neon-pink);
            background: rgba(255, 0, 234, 0.05);
        }
        .metrics-table tr:hover td {
            background: rgba(0, 243, 255, 0.1);
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        @keyframes pulse {
            0% { box-shadow: 0 4px 15px rgba(0, 243, 255, 0.2); }
            50% { box-shadow: 0 4px 25px rgba(0, 243, 255, 0.5); }
            100% { box-shadow: 0 4px 15px rgba(0, 243, 255, 0.2); }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(39,255,20,0.15) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.3;
            animation: scanline 6s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ Nuvola Orbital Command 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">OPTIMAL [SYS_CORE_V9.2]</span> | DATALINK: <span class="status-online">SECURE</span></p>
        <p class="status-online" style="margin-top: 10px; font-size: 1.2rem; text-shadow: 0 0 15px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <strong>🐺 SQUADRA_ALPHA</strong> <span style="font-size: 0.8em; color: #888;">[Scalper Binance]</span><br>
                Status: <span class="status-online">ENGAGED</span> | Ping: 12ms<br>
                <small style="color: #aaa;">Executing micro-arbitrage on BTC/USDT orderbook.</small>
            </div>
            <div class="item">
                <strong>🌊 SQUADRA_DELTA</strong> <span style="font-size: 0.8em; color: #888;">[Order Flow]</span><br>
                Status: <span class="status-online">MONITORING</span> | Ping: 18ms<br>
                <small style="color: #aaa;">Tracking liquidity sweeps & spoofs. Awaiting triggers.</small>
            </div>
            <div class="item">
                <strong>⚖️ SQUADRA_GAMMA</strong> <span style="font-size: 0.8em; color: #888;">[Pairs Trading Bitget]</span><br>
                Status: <span class="status-online">ACTIVE</span> | Ping: 25ms<br>
                <small style="color: #aaa;">Stat-arb deployed on ETH/SOL synthetic pairs.</small>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="item">
                <strong>🧛‍♂️ Lo Strozzino</strong> <span style="font-size: 0.8em; color: #888;">[Funding Arb]</span><br>
                Status: <span class="status-online">HARVESTING YIELD (BKG)</span><br>
                <small style="color: #aaa;">Continuous premium extraction via perpetual swaps.</small>
            </div>
            <div class="item">
                <strong>🧮 Il Contabile</strong> <span style="font-size: 0.8em; color: #888;">[DCA]</span><br>
                Status: <span class="status-online">ACCUMULATING (BKG)</span><br>
                <small style="color: #aaa;">Scheduled TWAP execution active. Slippage nominal.</small>
            </div>
            <div class="item">
                <strong>👼 L'Angelo Custode</strong> <span style="font-size: 0.8em; color: #888;">[MEV Arbitrum]</span><br>
                Status: <span class="status-online">DEFENDING (BKG)</span><br>
                <small style="color: #aaa;">Front-running protection & sandwiching defense active.</small>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="item">
                <strong>👁️ The Oracle</strong> <span style="font-size: 0.8em; color: #888;">[Binance Sentiment]</span>
                <table class="metrics-table">
                    <tr><th>Metric</th><th>Value</th><th>Status</th></tr>
                    <tr><td>Fear/Greed</td><td>78 (Extreme Greed)</td><td><span style="color:var(--neon-pink)">DANGER</span></td></tr>
                    <tr><td>Long/Short Ratio</td><td id="ls-ratio">1.45</td><td><span class="status-online">BULL BIAS</span></td></tr>
                    <tr><td>Volatility Index</td><td>42.5</td><td><span class="status-warning">ELEVATED</span></td></tr>
                </table>
            </div>
            <div class="item">
                <strong>🐋 Whale Tracker</strong> <span style="font-size: 0.8em; color: #888;">[On-Chain Flows]</span>
                <table class="metrics-table">
                    <tr><th>Asset</th><th>Volume (24h)</th><th>Alert</th></tr>
                    <tr><td>BTC</td><td>+45,210 BTC</td><td><span class="status-online">INFLOW</span></td></tr>
                    <tr><td>ETH</td><td>-120,500 ETH</td><td><span style="color:var(--neon-pink)">OUTFLOW</span></td></tr>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        // Simulate live data updates
        setInterval(() => {
            const ratio = (1.40 + Math.random() * 0.1).toFixed(2);
            document.getElementById('ls-ratio').innerText = ratio;
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
