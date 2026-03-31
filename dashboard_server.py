from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola Dashboard</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-purple: #b026ff;
            --neon-red: #ff003c;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px currentColor;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            color: var(--neon-cyan);
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.2);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-cyan); }
            50% { text-shadow: 0 0 20px var(--neon-cyan), 0 0 30px var(--neon-cyan); }
            100% { text-shadow: 0 0 5px var(--neon-cyan); }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(180deg, transparent 50%, rgba(0, 255, 0, 0.05) 50%);
            background-size: 100% 4px;
            pointer-events: none;
        }
        .panel.trinity {
            border-color: var(--neon-purple);
            color: var(--neon-purple);
            box-shadow: inset 0 0 10px rgba(176, 38, 255, 0.1), 0 0 10px rgba(176, 38, 255, 0.2);
        }
        .panel.metrics {
            border-color: var(--neon-cyan);
            color: var(--neon-cyan);
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.1), 0 0 10px rgba(0, 255, 255, 0.2);
        }
        .status-online {
            color: var(--neon-green);
            animation: blink 1s step-end infinite;
        }
        .status-warning {
            color: yellow;
        }
        @keyframes blink { 50% { opacity: 0; } }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(255,255,255,0.2); padding-bottom: 5px; }
        .badge {
            float: right;
            background: var(--neon-green);
            color: black;
            padding: 2px 5px;
            font-size: 0.8em;
            border-radius: 3px;
            font-weight: bold;
        }
        .panel.trinity .badge { background: var(--neon-purple); }
        .panel.metrics .badge { background: var(--neon-cyan); }
        
        .terminal {
            margin-top: 30px;
            background: black;
            border: 1px solid #333;
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.9em;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND UPLINK</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPTIME: 99.99% | SECURITY: MAXIMUM</p>
        <p style="font-size: 1.2em; font-weight: bold; color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>🐺 <b>SQUADRA_ALPHA</b> <br><small>Scalper su Binance</small> <span class="badge">ACTIVE</span></li>
                <li>🌊 <b>SQUADRA_DELTA</b> <br><small>Order Flow Analysis</small> <span class="badge">STANDBY</span></li>
                <li>⚖️ <b>SQUADRA_GAMMA</b> <br><small>Pairs Trading (Bitget)</small> <span class="badge">ACTIVE</span></li>
            </ul>
            <p style="font-size:0.8em; margin-top:15px; border-top:1px solid var(--neon-green); padding-top:5px;">&gt; LATENCY: 12ms | WIN RATE: 68.4%</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>👁️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>🕴️ <b>Lo Strozzino</b> <br><small>Funding Arbitrage (Perp/Spot)</small> <span class="badge">ONLINE</span></li>
                <li>🧮 <b>Il Contabile</b> <br><small>DCA Accumulation Engine</small> <span class="badge">ONLINE</span></li>
                <li>🛡️ <b>L'Angelo Custode</b> <br><small>MEV Protection & Sniper (Arbitrum)</small> <span class="badge">ONLINE</span></li>
            </ul>
            <p style="font-size:0.8em; margin-top:15px; border-top:1px solid var(--neon-purple); padding-top:5px;">&gt; BACKGROUND PROCESSES: SECURED</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>🔮 <b>The Oracle</b> <br><small>Binance Sentiment Index</small> <span class="badge" style="background:var(--neon-cyan);color:black;">BULLISH (78)</span></li>
                <li>🐋 <b>Whale Tracker</b> <br><small>Large Block Trades (>1M)</small> <span class="badge" style="background:var(--neon-cyan);color:black;">DETECTED: 4</span></li>
                <li>⚡ <b>Liquidity Heatmap</b> <br><small>Orderbook Imbalance</small> <span class="badge" style="background:var(--neon-cyan);color:black;">SKEWED LONG</span></li>
            </ul>
            <p style="font-size:0.8em; margin-top:15px; border-top:1px solid var(--neon-cyan); padding-top:5px;">&gt; DATA STREAMS: SYNCED</p>
        </div>
    </div>
    
    <div class="terminal">
        <p>> [SYSTEM] Nuvola Dashboard initialized.</p>
        <p>> [HFT] SQUADRA_ALPHA executing scalp long on BTC/USDT.</p>
        <p>> [TRINITY] Lo Strozzino collecting funding rate: +0.01%.</p>
        <p>> <span class="status-online">_</span></p>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
