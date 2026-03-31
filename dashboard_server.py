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
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            font-size: 2.5em;
            letter-spacing: 5px;
            text-transform: uppercase;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-top: 30px;
        }
        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2), 0 0 15px rgba(0, 255, 0, 0.3);
            position: relative;
        }
        .panel h2 {
            margin-top: 0;
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 10px;
            font-size: 1.2em;
        }
        .panel:nth-child(2) h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
        }
        .panel:nth-child(2) {
            border-color: var(--neon-pink);
            box-shadow: inset 0 0 10px rgba(255, 0, 255, 0.2), 0 0 15px rgba(255, 0, 255, 0.3);
        }
        .item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0, 50, 0, 0.3);
            border-left: 3px solid var(--neon-green);
            transition: all 0.3s ease;
        }
        .panel:nth-child(2) .item {
            background: rgba(50, 0, 50, 0.3);
            border-left: 3px solid var(--neon-pink);
        }
        .item:hover {
            transform: translateX(5px);
            background: rgba(0, 80, 0, 0.5);
        }
        .panel:nth-child(2) .item:hover {
            background: rgba(80, 0, 80, 0.5);
        }
        .status {
            animation: blink 2s infinite;
            font-weight: bold;
        }
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .metric-box {
            background: rgba(0, 0, 50, 0.5);
            border: 1px solid var(--neon-blue);
            padding: 10px;
            text-align: center;
        }
        .metric-value {
            font-size: 1.5em;
            color: #fff;
            text-shadow: 0 0 5px #fff;
            margin-top: 5px;
        }
        .scanline {
            width: 100%;
            height: 100px;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            position: fixed;
            bottom: 100%;
            pointer-events: none;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { bottom: 100%; }
            100% { bottom: -100px; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA </h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); border: 1px solid var(--neon-pink); padding: 10px; border-radius: 5px; background: rgba(50,0,50,0.3); animation: blink 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span>SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status" style="color: #0f0;">ONLINE 🟢</span>
            </div>
            <div class="item">
                <span>SQUADRA_DELTA (Order Flow)</span>
                <span class="status" style="color: #0f0;">ONLINE 🟢</span>
            </div>
            <div class="item">
                <span>SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status" style="color: #0f0;">ONLINE 🟢</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="item">
                <span>Lo Strozzino (Funding Arb)</span>
                <span class="status" style="color: var(--neon-pink);">ACTIVE ⚡</span>
            </div>
            <div class="item">
                <span>Il Contabile (DCA)</span>
                <span class="status" style="color: var(--neon-pink);">ACTIVE ⚡</span>
            </div>
            <div class="item">
                <span>L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status" style="color: var(--neon-pink);">GUARDING 🛡️</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-blue);">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); border-bottom-color: var(--neon-blue);">📊 METRICHE DI MERCATO</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: var(--neon-blue);">The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 🐂</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: var(--neon-blue);">Whale Tracker</div>
                    <div class="metric-value">DETECTED 🐋</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: var(--neon-blue);">Global Volatility</div>
                    <div class="metric-value">ELEVATED ⚠️</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.8em; color: var(--neon-blue);">System Load</div>
                    <div class="metric-value">12.4% 💻</div>
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
