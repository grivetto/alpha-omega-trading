from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #00ff00;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px #00ff00;
            margin-top: 0;
        }
        .glow-red { color: #ff0055; text-shadow: 0 0 10px #ff0055; }
        .glow-blue { color: #00f0ff; text-shadow: 0 0 10px #00f0ff; }
        .glow-yellow { color: #ffcc00; text-shadow: 0 0 10px #ffcc00; }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid #333;
            background: rgba(0, 20, 0, 0.3);
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, #00ff00, transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed #00ff00;
            margin-bottom: 10px;
            padding-bottom: 5px;
        }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .grid-data {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            text-align: center;
            font-size: 0.9em;
        }
        .data-box {
            border: 1px solid #00f0ff;
            padding: 10px;
            background: rgba(0, 240, 255, 0.05);
        }
    </style>
</head>
<body>
    <h1 style="text-align: center; font-size: 2.5em; border-bottom: 2px solid #00ff00; padding-bottom: 10px;">
        🛰️ NUVOLA ORBITAL COMMAND 🛰️
    </h1>
    <div style="text-align: center; margin-bottom: 30px;" class="glow-yellow blink">
        SYSTEM STATUS: ONLINE | SECURE CONNECTION ESTABLISHED
        <br><br>
        <span style="color: #00ff00; font-size: 1.2em; font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 class="glow-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🔴 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="blink">ENGAGING [142 ops/min]</span>
            </div>
            <div class="status">
                <span>🔵 SQUADRA_DELTA (Order Flow)</span>
                <span>STANDBY - SCANNING LIQUIDITY</span>
            </div>
            <div class="status">
                <span>🟡 SQUADRA_GAMMA (Bitget Pairs Trading)</span>
                <span>ACTIVE - HEDGED [0.98 CORR]</span>
            </div>
            <p class="glow-blue">> Total 24h PnL: +$1,432.50</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-blue">🧬 PROTOCOLLO TRINITY</h2>
            <div class="status">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span>ONLINE [Yield: 14.2% APY]</span>
            </div>
            <div class="status">
                <span>🧮 Il Contabile (DCA)</span>
                <span>ONLINE [Next buy: 4h 12m]</span>
            </div>
            <div class="status">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="blink">SNIPING MEMPOOL</span>
            </div>
            <p>> Trinity Shield: <span style="color: #00ff00">ACTIVE</span></p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div class="grid-data">
                <div class="data-box">
                    <div class="glow-blue">👁️ THE ORACLE</div>
                    <div style="font-size: 1.5em; margin-top: 5px;">BULLISH (78%)</div>
                    <div>Binance Sentiment Index</div>
                </div>
                <div class="data-box">
                    <div class="glow-red">🐋 WHALE TRACKER</div>
                    <div style="font-size: 1.5em; margin-top: 5px;">-$42.1M</div>
                    <div>Net Exchange Flow (1h)</div>
                </div>
                <div class="data-box">
                    <div class="glow-yellow">⚡ VOLATILITY INDEX</div>
                    <div style="font-size: 1.5em; margin-top: 5px;">ELEVATED</div>
                    <div>Action Recommended</div>
                </div>
            </div>
            <div style="margin-top: 15px; border: 1px dashed #333; padding: 10px;">
                <span class="glow-red">> </span> [SYS_LOG] Whale alert: 12,000 BTC moved to Binance.<br>
                <span class="glow-red">> </span> [SYS_LOG] SQUADRA_ALPHA adjusting spread margins.<br>
                <span class="glow-red">> </span> [SYS_LOG] Funding rates shifting negative on SOL/USDT. Lo Strozzino rebalancing.
            </div>
        </div>
    </div>

    <script>
        // Simple random data updater to make it feel alive
        setInterval(() => {
            const elements = document.querySelectorAll('.blink');
            elements.forEach(el => {
                if (Math.random() > 0.8) {
                    el.style.visibility = el.style.visibility === 'hidden' ? 'visible' : 'hidden';
                }
            });
        }, 500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
