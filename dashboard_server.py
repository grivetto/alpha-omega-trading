from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0fa;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
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
        }
        h1 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 40px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.1), inset 0 0 20px rgba(0, 255, 255, 0.05);
            padding: 20px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.3), inset 0 0 30px rgba(0, 255, 255, 0.1);
            transform: translateY(-2px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
            background: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue);
        }
        .panel.pink { border-color: rgba(255, 0, 255, 0.4); box-shadow: 0 0 10px rgba(255, 0, 255, 0.1); }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }
        .panel.pink:hover { box-shadow: 0 0 15px rgba(255, 0, 255, 0.3); }
        
        .panel.green { border-color: rgba(0, 255, 170, 0.4); box-shadow: 0 0 10px rgba(0, 255, 170, 0.1); }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 15px var(--neon-green); }
        .panel.green:hover { box-shadow: 0 0 15px rgba(0, 255, 170, 0.3); }

        h2 {
            margin-top: 0;
            font-size: 1.2em;
            color: #fff;
            text-shadow: 0 0 5px #fff;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.2);
            padding-bottom: 10px;
        }
        .status {
            color: var(--neon-green);
            font-size: 0.7em;
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
            padding: 3px 6px;
            border: 1px solid var(--neon-green);
            border-radius: 3px;
            background: rgba(0, 255, 170, 0.1);
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        ul { list-style-type: none; padding: 0; margin-bottom: 20px;}
        li { margin-bottom: 12px; font-size: 0.95em; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .metric-value { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); font-weight: bold; }
        .panel.blue .metric-value { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .panel.green .metric-value { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }

        .log-box { 
            height: 120px; 
            overflow-y: auto; 
            font-size: 0.85em; 
            color: #ccc; 
            background: rgba(0,0,0,0.6); 
            padding: 10px; 
            border: 1px solid #333;
            border-radius: 3px;
            font-family: monospace;
        }
        .log-box span.time { color: #666; margin-right: 5px; }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #111; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--neon-blue); }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA ☁️</h1>

    <div style="text-align: center; margin-bottom: 30px; font-size: 1.2em; color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); border: 1px solid var(--neon-pink); padding: 10px; border-radius: 4px; background: rgba(255, 0, 255, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel blue">
            <h2>⚔️ SQUADRE D'ASSALTO <span class="status">LIVE [ENGAGED]</span></h2>
            <ul>
                <li><span>🐺 <b>SQUADRA_ALPHA</b> <br><small style="color:#888">Binance Scalper</small></span> <span class="metric-value">+2.4% / 24h</span></li>
                <li><span>🌊 <b>SQUADRA_DELTA</b> <br><small style="color:#888">Order Flow</small></span> <span class="metric-value">ACTIVE</span></li>
                <li><span>⚖️ <b>SQUADRA_GAMMA</b> <br><small style="color:#888">Bitget Pairs</small></span> <span class="metric-value">HEDGING</span></li>
            </ul>
            <div class="log-box">
                <span class="time">[10:59:01]</span> [ALPHA] Executed long BTC @ 64200.5<br>
                <span class="time">[10:58:44]</span> [DELTA] Order book imbalance detected on ETH/USDT<br>
                <span class="time">[10:55:12]</span> [GAMMA] Rebalancing ETH/BTC pair<br>
                <span class="time">[10:50:00]</span> [SYS] HFT modules operating nominally<br>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <h2>🔺 PROTOCOLLO TRINITY <span class="status">BACKGROUND ACTIVE</span></h2>
            <ul>
                <li><span>🦈 <b>Lo Strozzino</b> <br><small style="color:#888">Funding Arb</small></span> <span class="metric-value" style="color:var(--neon-pink)">14.2% APY</span></li>
                <li><span>🧮 <b>Il Contabile</b> <br><small style="color:#888">DCA Bot</small></span> <span class="metric-value" style="color:var(--neon-pink)">ACCUMULATING</span></li>
                <li><span>👼 <b>L'Angelo Custode</b> <br><small style="color:#888">MEV Arbitrum</small></span> <span class="metric-value" style="color:var(--neon-pink)">SCANNING MEMPOOL</span></li>
            </ul>
            <div class="log-box" style="color: #e8a">
                <span class="time">[10:52:10]</span> [STROZZINO] Rebalancing perpetual exposure<br>
                <span class="time">[08:00:05]</span> [CONTABILE] Daily buy executed (0.015 BTC)<br>
                <span class="time">[10:58:22]</span> [ANGELO] Sandwich attack avoided on Uniswap V3<br>
                <span class="time">[10:58:25]</span> [ANGELO] Searching for arb opportunities...<br>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h2>📊 THE ORACLE & METRICS <span class="status">SYNCED</span></h2>
            <ul>
                <li><span>🔮 <b>Binance Sentiment</b> <br><small style="color:#888">The Oracle</small></span> <span class="metric-value">GREED (78)</span></li>
                <li><span>🐋 <b>Whale Tracker</b> <br><small style="color:#888">On-chain Flow</small></span> <span class="metric-value">OUTFLOW DETECTED</span></li>
                <li><span>⚡ <b>Network Gwei</b> <br><small style="color:#888">Ethereum Mainnet</small></span> <span class="metric-value">12 Gwei</span></li>
                <li><span>🎯 <b>Orbital Win Rate</b> <br><small style="color:#888">Last 7 days</small></span> <span class="metric-value">68.5%</span></li>
            </ul>
            <div class="log-box" style="color: #8e8">
                <span class="time">[10:59:10]</span> [ORACLE] BTC dominance increasing (+0.2%)<br>
                <span class="time">[10:56:40]</span> [WHALE] 1500 BTC moved off CEX (Binance -> Unknown)<br>
                <span class="time">[10:55:00]</span> [SYS] Market volatility indicator: LOW<br>
                <span class="time">[10:45:00]</span> [SYS] Oracle model weights updated successfully<br>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return HTML_CONTENT

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
