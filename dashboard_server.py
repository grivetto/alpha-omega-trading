import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-purple: #bc13fe;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(0deg, transparent 24%, rgba(57, 255, 20, .05) 25%, rgba(57, 255, 20, .05) 26%, transparent 27%, transparent 74%, rgba(57, 255, 20, .05) 75%, rgba(57, 255, 20, .05) 76%, transparent 77%, transparent), 
                linear-gradient(90deg, transparent 24%, rgba(57, 255, 20, .05) 25%, rgba(57, 255, 20, .05) 26%, transparent 27%, transparent 74%, rgba(57, 255, 20, .05) 75%, rgba(57, 255, 20, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
            font-size: 2.5em;
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 10px rgba(57, 255, 20, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(57, 255, 20, 0.2), transparent);
            animation: scanline 4s linear infinite;
        }
        @keyframes scanline {
            100% { left: 200%; }
        }
        .panel h2 {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
            border-bottom: 1px dashed var(--neon-purple);
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.2em;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 1.5s infinite;
        }
        .status-standby {
            color: #ffb400;
            text-shadow: 0 0 5px #ffb400;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
        }
        .value {
            color: var(--neon-cyan);
            font-weight: bold;
        }
        .section-title {
            font-weight: bold;
            color: #fff;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA // ORBITAL COMMAND 🛰️</h1>
    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row"><span class="section-title">🐺 SQUADRA_ALPHA (Binance Scalp)</span><span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Engine Latency</span><span class="value">12ms</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Session PnL</span><span class="value">+42.50 USDT</span></div>
            <br>
            <div class="data-row"><span class="section-title">🦅 SQUADRA_DELTA (Order Flow)</span><span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Imbalance Detected</span><span class="value">BTC/USDT (Long)</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Win Rate</span><span class="value">68.4%</span></div>
            <br>
            <div class="data-row"><span class="section-title">🦈 SQUADRA_GAMMA (Bitget Pairs)</span><span class="status-online">[ ENGAGED ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Active Pair</span><span class="value">ETH/SOL</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Z-Score</span><span class="value">2.41</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="data-row" style="margin-bottom: 15px; border-bottom: 1px solid var(--neon-cyan); padding-bottom: 5px;">
                <span class="status-online" style="font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <div class="data-row"><span class="section-title">🕴️ Lo Strozzino (Funding Arb)</span><span class="status-online">[ ACTIVE ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Target Asset</span><span class="value">XRP Perp vs Spot</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Spread Yield</span><span class="value">14.2% APY</span></div>
            <br>
            <div class="data-row"><span class="section-title">🧮 Il Contabile (DCA)</span><span class="status-standby">[ STANDBY ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Next Execution</span><span class="value">T-minus 04:12:00</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Vault Balance</span><span class="value">15,000 USDC</span></div>
            <br>
            <div class="data-row"><span class="section-title">👼 L'Angelo Custode (Arbitrum MEV)</span><span class="status-online">[ HUNTING ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Mempool Scanner</span><span class="value">Synced (Block 182M)</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Flashbots Relay</span><span class="value">Connected</span></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 MARKET INTEL</h2>
            <div class="data-row"><span class="section-title">👁️ THE ORACLE (Sentiment)</span><span class="status-online">[ STREAMING ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Fear & Greed Index</span><span class="value">78 (Extreme Greed)</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Binance Long/Short Ratio</span><span class="value">1.45</span></div>
            <br>
            <div class="data-row"><span class="section-title">🐋 WHALE TRACKER</span><span class="status-online">[ ACTIVE ]</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Last Alert</span><span class="value">500 BTC to Coinbase</span></div>
            <div class="data-row"><span>&nbsp;&nbsp;&gt; Netflow (24h)</span><span class="value">-12,400 BTC</span></div>
            <br>
            <hr style="border: 0; border-bottom: 1px solid var(--neon-green); opacity: 0.3;">
            <div class="data-row" style="margin-top: 10px;"><span>📡 ORBITAL UPLINK</span><span class="value">ESTABLISHED</span></div>
            <div class="data-row"><span>🛡️ CORE UPTIME</span><span class="value">99.99%</span></div>
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
