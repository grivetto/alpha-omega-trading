from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .panel:hover {
            box-shadow: 0 0 20px var(--neon-blue);
            transform: translateY(-2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        .title-squads { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); border-color: var(--neon-red); }
        .title-trinity { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); border-color: var(--neon-pink); }
        .title-metrics { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); border-color: var(--neon-green); }
        
        .panel.squads { border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 60, 0.2); }
        .panel.squads:hover { box-shadow: 0 0 20px var(--neon-red); }
        .panel.trinity { border-color: var(--neon-pink); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); }
        .panel.trinity:hover { box-shadow: 0 0 20px var(--neon-pink); }
        .panel.metrics { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(57, 255, 20, 0.2); }
        .panel.metrics:hover { box-shadow: 0 0 20px var(--neon-green); }

        ul { list-style-type: none; padding: 0; }
        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-blue);
        }
        .squads li { border-left-color: var(--neon-red); }
        .trinity li { border-left-color: var(--neon-pink); }
        .metrics li { border-left-color: var(--neon-green); }
        
        .status { float: right; font-weight: bold; animation: pulse 2s infinite; }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status.active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status.standby { color: #ffeb3b; text-shadow: 0 0 5px #ffeb3b; }
        
        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; }
            100% { opacity: 0.8; }
        }
        
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .data-cell {
            background: rgba(255,255,255,0.05);
            padding: 5px;
            text-align: center;
            border: 1px dashed rgba(255,255,255,0.2);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌌 ORBITAL COMMAND - NUVOLA 🌌</h1>
        <p>SYSTEM STATUS: <span class="status online" style="float:none;">SECURE & ONLINE</span> | QUANTITATIVE TACTICAL DASHBOARD</p>
        <p style="color: var(--neon-pink); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 8px var(--neon-pink); margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- ASSAULT SQUADS -->
        <div class="panel squads">
            <h2 class="title-squads">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong> <span class="status active">ENGAGED</span><br>
                    <small>Scalper | Target: Binance Futures</small>
                    <div class="data-grid">
                        <div class="data-cell">Win Rate: 68.4%</div>
                        <div class="data-cell">Latency: 12ms</div>
                    </div>
                </li>
                <li>
                    <strong>🦅 SQUADRA_DELTA</strong> <span class="status active">SCANNING</span><br>
                    <small>Order Flow & Imbalance Detection</small>
                    <div class="data-grid">
                        <div class="data-cell">Books: 42 Tracked</div>
                        <div class="data-cell">Spoofing: Detected</div>
                    </div>
                </li>
                <li>
                    <strong>🐍 SQUADRA_GAMMA</strong> <span class="status standby">STANDBY</span><br>
                    <small>Pairs Trading | Target: Bitget</small>
                    <div class="data-grid">
                        <div class="data-cell">Spread Z-Score: 1.2</div>
                        <div class="data-cell">Capital: 100%</div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel trinity">
            <h2 class="title-trinity">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🎩 Lo Strozzino</strong> <span class="status online">ONLINE</span><br>
                    <small>Background: Funding Rate Arbitrage</small>
                    <div class="data-grid">
                        <div class="data-cell">Yield Est: +18.4% APY</div>
                        <div class="data-cell">Exposure: Neutral</div>
                    </div>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> <span class="status online">ONLINE</span><br>
                    <small>Background: Strategic DCA & Rebalancing</small>
                    <div class="data-grid">
                        <div class="data-cell">Next Buy: 14h 22m</div>
                        <div class="data-cell">Deviation: 2.1%</div>
                    </div>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> <span class="status online">ONLINE</span><br>
                    <small>Background: MEV Protection & Arb | Arbitrum</small>
                    <div class="data-grid">
                        <div class="data-cell">Mempool: Safe</div>
                        <div class="data-cell">Blocks Sniped: 3</div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel metrics">
            <h2 class="title-metrics">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <strong>👁️ The Oracle</strong> <span class="status active">ANALYZING</span><br>
                    <small>Binance Sentiment Index</small>
                    <div class="data-grid">
                        <div class="data-cell" style="color:var(--neon-green)">Greed: 72/100</div>
                        <div class="data-cell">Trend: Bullish</div>
                    </div>
                </li>
                <li>
                    <strong>🐋 Whale Tracker</strong> <span class="status active">TRACKING</span><br>
                    <small>On-Chain Large Transactions</small>
                    <div class="data-grid">
                        <div class="data-cell">Recent: +5,000 ETH (Inflow)</div>
                        <div class="data-cell">Alert Level: ELEVATED</div>
                    </div>
                </li>
                <li>
                    <strong>🌐 Global Liquidity</strong><br>
                    <small>Macro Indicators</small>
                    <div class="data-grid">
                        <div class="data-cell">USDT Dominance: 4.8%</div>
                        <div class="data-cell">VIX: 14.2</div>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run securely and quietly
    app.run(host='0.0.0.0', port=5000, debug=False)
