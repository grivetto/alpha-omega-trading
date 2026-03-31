from flask import Flask, render_template_string

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
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-color: #050510;
            --panel-bg: rgba(10, 10, 20, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: #fff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: pulse 2s infinite alternate;
        }
        @keyframes pulse {
            from { text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); }
            to { text-shadow: 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan), 0 0 40px var(--neon-cyan); }
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-magenta);
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-magenta));
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .panel h2 {
            color: var(--neon-magenta);
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 5px;
            margin-top: 0;
            font-size: 1.2em;
        }
        .status-online { color: #0f0; text-shadow: 0 0 5px #0f0; }
        .status-standby { color: #ff0; text-shadow: 0 0 5px #ff0; }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-left: 2px solid var(--neon-cyan); padding-left: 10px; }
        .metric-box {
            background: rgba(0, 255, 255, 0.1);
            border: 1px solid var(--neon-cyan);
            padding: 10px;
            margin-top: 10px;
            text-align: center;
            font-size: 1.1em;
            box-shadow: inset 0 0 10px rgba(0, 255, 255, 0.2);
        }
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPLINK: SECURE</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    Role: Scalper (Binance)<br>
                    Status: <span class="status-online">ENGAGING TARGETS</span><br>
                    <small>Win Rate: 68.4% | Latency: 12ms</small>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    Role: Order Flow Analysis<br>
                    Status: <span class="status-online">MONITORING</span><br>
                    <small>Imbalance detected: BTC/USDT</small>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐍<br>
                    Role: Pairs Trading (Bitget)<br>
                    Status: <span class="status-standby">AWAITING SPREAD</span><br>
                    <small>Target Spread: > 0.5%</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="metric-box" style="color: #0f0; border-color: #0f0; box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2); margin-bottom: 15px;">
                <span class="blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🕴️<br>
                    Role: Funding Rate Arbitrage<br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    <small>Harvesting yields across perpetuals</small>
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮<br>
                    Role: Dynamic DCA<br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    <small>Accumulating spot assets</small>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 🛡️<br>
                    Role: MEV Protection & Arb (Arbitrum)<br>
                    Status: <span class="status-online">ACTIVE IN BACKGROUND</span><br>
                    <small>Guarding mempool transactions</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p style="margin-bottom: 2px;"><strong>The Oracle</strong> 🔮 (Binance Sentiment):</p>
            <div class="metric-box" style="color: #0f0; border-color: #0f0; box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2);">
                BULLISH CONFIDENCE: 74%
            </div>
            
            <p style="margin-bottom: 2px; margin-top: 15px;"><strong>Whale Tracker</strong> 🐋:</p>
            <div class="metric-box">
                LAST ALERT: 500 BTC moved to Coinbase<br>
                <small style="color: var(--neon-magenta);">Impact: Low</small>
            </div>
            
            <p style="margin-bottom: 2px; margin-top: 15px;"><strong>Global Liquidity</strong> 💧:</p>
            <div class="metric-box" style="font-family: monospace;">
                [████████░░] 80%
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
