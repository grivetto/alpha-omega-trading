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
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-purple: #b026ff;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .glow-text {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .glow-text-cyan {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 10px var(--neon-cyan);
        }
        .glow-text-purple {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple), 0 0 10px var(--neon-purple);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
            pointer-events: none;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1.5s infinite alternate;
        }
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(0,255,0,0.3);
            margin-bottom: 5px;
            padding-bottom: 2px;
        }
        .data-label { color: #888; }
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 10vh;
            background: linear-gradient(to bottom, rgba(0,255,0,0), rgba(0,255,0,0.1), rgba(0,255,0,0));
            animation: scan 6s linear infinite;
            pointer-events: none;
            z-index: 100;
        }
        @keyframes scan {
            0% { top: -10vh; }
            100% { top: 110vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1 class="glow-text">🌐 NUVOLA // ORBITAL COMMAND 🌐</h1>
        <p>SYSTEM STATUS: <span class="glow-text">ONLINE</span> | UPLINK: <span class="glow-text">SECURE</span></p>
        <p class="glow-text-purple" style="font-weight: bold; font-size: 1.2em; border: 1px solid var(--neon-purple); padding: 5px; display: inline-block; background: rgba(176, 38, 255, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="glow-text-cyan">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span class="data-label">SQUADRA_ALPHA (Binance Scalper)</span>
                <span><div class="status-indicator"></div> ACTIVE</span>
            </div>
            <div class="data-row">
                <span class="data-label">⚡ Win Rate (1h)</span>
                <span class="glow-text-cyan">87.4%</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">SQUADRA_DELTA (Order Flow)</span>
                <span><div class="status-indicator"></div> ACTIVE</span>
            </div>
            <div class="data-row">
                <span class="data-label">🎯 Imbalance Detected</span>
                <span class="glow-text-cyan">14 req/s</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">SQUADRA_GAMMA (Bitget Pairs)</span>
                <span><div class="status-indicator"></div> ACTIVE</span>
            </div>
            <div class="data-row">
                <span class="data-label">⚖️ Spread Z-Score</span>
                <span class="glow-text-cyan">+2.41 (Short)</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-text-purple">🔺 PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span class="data-label">Lo Strozzino (Funding Arb)</span>
                <span><div class="status-indicator" style="background:var(--neon-purple);box-shadow:0 0 8px var(--neon-purple)"></div> BACKGROUND</span>
            </div>
            <div class="data-row">
                <span class="data-label">💸 Est. APY</span>
                <span class="glow-text-purple">18.2%</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">Il Contabile (DCA)</span>
                <span><div class="status-indicator" style="background:var(--neon-purple);box-shadow:0 0 8px var(--neon-purple)"></div> BACKGROUND</span>
            </div>
            <div class="data-row">
                <span class="data-label">💼 Next Buy Window</span>
                <span class="glow-text-purple">4h 12m</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">L'Angelo Custode (MEV Arbitrum)</span>
                <span><div class="status-indicator" style="background:var(--neon-purple);box-shadow:0 0 8px var(--neon-purple)"></div> BACKGROUND</span>
            </div>
            <div class="data-row">
                <span class="data-label">🛡️ Sandwich Protection</span>
                <span class="glow-text-purple">ARMED</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="glow-text">📊 MARKET INTELLIGENCE</h2>
            <div class="data-row">
                <span class="data-label">👁️ THE ORACLE (Sentiment)</span>
                <span class="glow-text">EXTREME GREED (88)</span>
            </div>
            <div class="data-row">
                <span class="data-label">Long/Short Ratio</span>
                <span class="glow-text">1.45</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">🐋 WHALE TRACKER</span>
                <span class="glow-text">PING: HIGH</span>
            </div>
            <div class="data-row">
                <span class="data-label">Recent Large Tx</span>
                <span class="glow-text">24,500 ETH -> Binance</span>
            </div>
            <br>
            <div class="data-row">
                <span class="data-label">CVD (Cumulative Vol. Delta)</span>
                <span style="color: #f00;">-4.2M (Selling Pressure)</span>
            </div>
            <div class="data-row">
                <span class="data-label">VIX (Crypto Volatility)</span>
                <span class="glow-text">64.5</span>
            </div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const els = document.querySelectorAll('.data-row:nth-child(even) span:last-child');
            if(Math.random() > 0.5 && els.length > 0) {
                const idx = Math.floor(Math.random() * els.length);
                els[idx].style.opacity = (Math.random() * 0.5 + 0.5);
            }
        }, 300);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
