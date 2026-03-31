from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-purple: #bc13fe;
            --dark-bg: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }
        .header h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            font-size: 2.5em;
            letter-spacing: 5px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(to right, transparent, rgba(0, 255, 255, 0.1), transparent);
            transform: skewX(-20deg);
            animation: scanline 4s infinite linear;
        }
        .panel h2 {
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 10px;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status {
            font-weight: bold;
            animation: blink 1s infinite alternate;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status.standby { color: #ffa500; text-shadow: 0 0 5px #ffa500; }
        .status.active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; text-shadow: 0 0 15px var(--neon-cyan); }
            100% { opacity: 0.8; }
        }
        @keyframes blink {
            from { opacity: 1; }
            to { opacity: 0.5; }
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            text-align: center;
        }
        .metric-value {
            font-size: 1.5em;
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
            margin-top: 5px;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND</h1>
        <p>NUVOLA QUANTITATIVE TERMINAL | SYSTEM: ONLINE | AUTH: VERIFIED</p>
        <div style="margin-top: 10px; padding: 10px; border: 1px dashed var(--neon-purple); display: inline-block; background-color: rgba(188, 19, 254, 0.1);">
            <span style="color: var(--neon-purple); font-weight: bold; text-shadow: 0 0 8px var(--neon-purple); font-size: 1.1em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span><i class="icon">🐺</i> SQUADRA_ALPHA (Binance Scalper)</span>
                    <span class="status active">[ ENGAGED ]</span>
                </li>
                <li>
                    <span><i class="icon">🌊</i> SQUADRA_DELTA (Order Flow)</span>
                    <span class="status online">[ STANDING BY ]</span>
                </li>
                <li>
                    <span><i class="icon">⚖️</i> SQUADRA_GAMMA (Bitget Pairs)</span>
                    <span class="status active">[ ARBITRAGE ACTIVE ]</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span><i class="icon">🦈</i> Lo Strozzino (Funding Arb)</span>
                    <span class="status online">[ ONLINE ]</span>
                </li>
                <li>
                    <span><i class="icon">🏦</i> Il Contabile (DCA / Staking)</span>
                    <span class="status online">[ BACKGROUND ]</span>
                </li>
                <li>
                    <span><i class="icon">🛡️</i> L'Angelo Custode (MEV Arbitrum)</span>
                    <span class="status standby">[ WATCHING ]</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>🔮 The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>🐳 Whale Tracker</div>
                    <div class="metric-value">ACCUMULATION</div>
                </div>
                <div class="metric-box">
                    <div>⚡ Volatility Index</div>
                    <div class="metric-value">ELEVATED</div>
                </div>
                <div class="metric-box">
                    <div>📡 Network Latency</div>
                    <div class="metric-value">12ms</div>
                </div>
            </div>
        </div>
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
