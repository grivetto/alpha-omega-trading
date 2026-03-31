from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-green: #39ff14;
            --bg-dark: #050505;
            --bg-panel: #111;
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-cyan);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
            margin-top: 0;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-magenta);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 4s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--bg-panel);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0,255,255,0.1), 0 0 10px rgba(0,255,255,0.2);
            position: relative;
        }
        .panel.alert {
            border-color: var(--neon-magenta);
            box-shadow: inset 0 0 15px rgba(255,0,255,0.1), 0 0 10px rgba(255,0,255,0.2);
        }
        .panel.safe {
            border-color: var(--neon-green);
            box-shadow: inset 0 0 15px rgba(57,255,20,0.1), 0 0 10px rgba(57,255,20,0.2);
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite;
        }
        .status-indicator.magenta {
            background-color: var(--neon-magenta);
            box-shadow: 0 0 5px var(--neon-magenta), 0 0 10px var(--neon-magenta);
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            border-bottom: 1px dotted rgba(0,255,255,0.3);
            font-size: 0.9em;
        }
        .title {
            font-weight: bold;
            font-size: 1.1em;
            margin-top: 15px;
            margin-bottom: 5px;
            color: #fff;
            text-shadow: 0 0 3px #fff;
        }
        .value {
            color: var(--neon-green);
            font-weight: bold;
        }
        .value.negative { color: var(--neon-magenta); }
        .value.neutral { color: var(--neon-cyan); }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 24%, 55% { opacity: 0.5; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,255,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.15;
            animation: scan 8s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND 🌐</h1>
        <h3>[ NUVOLA QUANTITATIVE DASHBOARD_v3.0 ]</h3>
        <p>SYSTEM: <span class="status-indicator"></span> <span style="color:var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">ONLINE & FULLY OPERATIONAL</span></p>
        <p style="color:var(--neon-cyan); font-weight:bold; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel alert">
            <h2 style="color:var(--neon-magenta);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="title">🐺 SQUADRA_ALPHA <span class="status-indicator magenta" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">Scalper (Binance)</span></div>
            <div class="data-row"><span>Target:</span> <span class="value neutral">BTC/USDT, ETH/USDT</span></div>
            <div class="data-row"><span>Win Rate (24h):</span> <span class="value">68.4%</span></div>
            <div class="data-row"><span>PnL (24h):</span> <span class="value">+$420.50</span></div>

            <div class="title">⚡ SQUADRA_DELTA <span class="status-indicator magenta" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">Order Flow</span></div>
            <div class="data-row"><span>Target:</span> <span class="value neutral">Liquidations & Imbalances</span></div>
            <div class="data-row"><span>Latency:</span> <span class="value">12ms</span></div>
            <div class="data-row"><span>Executions:</span> <span class="value neutral">1,024</span></div>

            <div class="title">⚖️ SQUADRA_GAMMA <span class="status-indicator magenta" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">Pairs Trading (Bitget)</span></div>
            <div class="data-row"><span>Z-Score:</span> <span class="value negative">-2.1 (Active)</span></div>
            <div class="data-row"><span>Exposure:</span> <span class="value neutral">$2,500</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel safe">
            <h2 style="color:var(--neon-green);">🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="title">🕴️ Lo Strozzino <span class="status-indicator" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">Funding Arb</span></div>
            <div class="data-row"><span>Status:</span> <span class="value">Harvesting Yield</span></div>
            <div class="data-row"><span>Est. APY:</span> <span class="value">14.2%</span></div>

            <div class="title">🧮 Il Contabile <span class="status-indicator" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">DCA Manager</span></div>
            <div class="data-row"><span>Status:</span> <span class="value">Accumulating</span></div>
            <div class="data-row"><span>Next Buy In:</span> <span class="value neutral" id="timer">02:14:00</span></div>

            <div class="title">👼 L'Angelo Custode <span class="status-indicator" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">MEV (Arbitrum)</span></div>
            <div class="data-row"><span>Status:</span> <span class="value">Guarding Mempool</span></div>
            <div class="data-row"><span>Sandwiches:</span> <span class="value">3 (24h)</span></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            
            <div class="title">🔮 The Oracle <span class="status-indicator" style="float:right;"></span></div>
            <div class="data-row"><span>Role:</span> <span class="value neutral">Binance Sentiment</span></div>
            <div class="data-row"><span>Fear & Greed:</span> <span class="value">64 (Greed)</span></div>
            <div class="data-row"><span>Long/Short Ratio:</span> <span class="value negative">0.89</span></div>

            <div class="title">🐋 Whale Tracker <span class="status-indicator" style="float:right;"></span></div>
            <div class="data-row"><span>Status:</span> <span class="value neutral">Scanning On-Chain</span></div>
            <div class="data-row"><span>Large Txs (1h):</span> <span class="value">14 Alerts</span></div>
            <div class="data-row"><span>Net Flow:</span> <span class="value negative">-4,500 BTC</span></div>

            <div class="title">📡 System Telemetry</div>
            <div class="data-row"><span>Global Latency:</span> <span class="value">14ms</span></div>
            <div class="data-row"><span>CPU Load:</span> <span class="value">12%</span></div>
            <div class="data-row"><span>RAM:</span> <span class="value">1.4 GB / 8 GB</span></div>
        </div>
    </div>
    
    <script>
        // Simulate real-time updates
        setInterval(() => {
            let lat = document.querySelectorAll('.data-row')[14].querySelectorAll('.value')[0];
            lat.innerText = (12 + Math.random() * 5).toFixed(0) + 'ms';
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
