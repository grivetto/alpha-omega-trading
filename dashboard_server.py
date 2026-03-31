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
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
        }
        h1 { font-size: 2.5em; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; }
        .container { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-top: 30px; }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset;
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 1.5s infinite; }
        .status-warning { color: yellow; text-shadow: 0 0 5px yellow; }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(0, 255, 255, 0.3); padding-bottom: 5px; display: flex; justify-content: space-between;}
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; text-align: center; }
        .metric-box { border: 1px solid var(--neon-pink); padding: 10px; box-shadow: 0 0 10px rgba(255, 0, 255, 0.2) inset; }
        .metric-value { font-size: 1.5em; color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .glitch { animation: glitch 1s linear infinite; }
        @keyframes glitch {
            2%, 64% { transform: translate(2px, 0) skew(0deg); }
            4%, 60% { transform: translate(-2px, 0) skew(0deg); }
            62% { transform: translate(0, 0) skew(5deg); }
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <h3 class="status-online">● SYSTEM ONLINE - TERMINAL SECURE</h3>
    <h3 style="color: yellow; text-shadow: 0 0 5px yellow;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 <b>SQUADRA_ALPHA</b> (Scalper Binance)</span> <span class="status-active">ENGAGED</span></li>
                <li><span>🌊 <b>SQUADRA_DELTA</b> (Order Flow)</span> <span class="status-online">MONITORING</span></li>
                <li><span>⚖️ <b>SQUADRA_GAMMA</b> (Pairs Bitget)</span> <span class="status-active">ARBITRAGE</span></li>
            </ul>
            <div style="font-size: 0.8em; margin-top: 15px; opacity: 0.7;">> Latency: 12ms | Exec: High-Freq</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🕴️ <b>Lo Strozzino</b> (Funding Arb)</span> <span class="status-online">YIELDING</span></li>
                <li><span>🧮 <b>Il Contabile</b> (DCA)</span> <span class="status-online">ACCUMULATING</span></li>
                <li><span>👼 <b>L'Angelo Custode</b> (MEV Arbitrum)</span> <span class="status-active">PROTECTING</span></li>
            </ul>
            <div style="font-size: 0.8em; margin-top: 15px; opacity: 0.7;">> Background Daemons: 3/3 ONLINE</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>👁️ The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>🐋 Whale Tracker</div>
                    <div class="metric-value glitch">INFLOW +$42M</div>
                </div>
                <div class="metric-box">
                    <div>🔥 Volatility Index</div>
                    <div class="metric-value">ELEVATED</div>
                </div>
                <div class="metric-box">
                    <div>💧 Liq. Sweep</div>
                    <div class="metric-value status-warning">PENDING</div>
                </div>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; font-size: 0.8em; opacity: 0.5;">
        WARNING: UNAUTHORIZED ACCESS WILL TRIGGER COUNTER-MEASURES.
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
