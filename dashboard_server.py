from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        body {
            background-color: #050505;
            color: #00ff00;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(circle at 50% 50%, #1a1a1a 0%, #000 100%);
            height: 100vh;
            overflow: hidden;
        }
        h1, h2 {
            text-shadow: 0 0 15px #0ff;
            text-align: center;
            text-transform: uppercase;
            border-bottom: 2px solid #0ff;
            padding-bottom: 10px;
            color: #e0ffff;
            letter-spacing: 2px;
        }
        h2 {
            font-size: 1.2em;
            color: #0f0;
            border: none;
            text-shadow: 0 0 8px #0f0;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-around;
            margin-top: 40px;
        }
        .card {
            background-color: rgba(10, 10, 10, 0.9);
            border: 1px solid #0ff;
            box-shadow: 0 0 15px #0ff, inset 0 0 10px #0ff;
            border-radius: 8px;
            padding: 20px;
            margin: 15px;
            width: 28%;
            min-width: 320px;
            transition: transform 0.3s, box-shadow 0.3s;
            backdrop-filter: blur(5px);
        }
        .card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 0 25px #f0f, inset 0 0 15px #f0f;
            border-color: #f0f;
        }
        .card h3 {
            color: #0ff;
            text-shadow: 0 0 10px #0ff;
            border-bottom: 1px dashed #0ff;
            padding-bottom: 8px;
            margin-top: 0;
            font-size: 1.3em;
        }
        .status {
            color: #ff0055;
            font-weight: bold;
            text-shadow: 0 0 8px #ff0055;
            animation: pulse 1.5s infinite;
        }
        .status.online {
            color: #00ff00;
            text-shadow: 0 0 8px #00ff00;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin: 15px 0;
            font-size: 1.05em;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(0, 255, 0, 0.2);
            padding-bottom: 5px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 0, 0.2);
            padding: 10px 0;
            font-size: 1.1em;
        }
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 100;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2>Nuvola Dashboard - Quantitative Tactical Interface</h2>
    <div style="text-align: center; margin-top: 15px; font-size: 1.2em; color: #f0f; text-shadow: 0 0 10px #f0f; animation: pulse 2s infinite;">
        <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
    </div>
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="card">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            <ul>
                <li><span>⚡ <strong>SQUADRA_ALPHA</strong><br><small>Scalper su Binance</small></span> <span class="status">ATTIVA</span></li>
                <li><span>🌊 <strong>SQUADRA_DELTA</strong><br><small>Order Flow</small></span> <span class="status">IN AGGUATO</span></li>
                <li><span>⚖️ <strong>SQUADRA_GAMMA</strong><br><small>Pairs Trading su Bitget</small></span> <span class="status">ALLINEATA</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="card" style="border-color: #f0f; box-shadow: 0 0 15px #f0f, inset 0 0 10px #f0f;">
            <h3 style="color: #f0f; text-shadow: 0 0 10px #f0f; border-color: #f0f;">🛡️ PROTOCOLLO TRINITY</h3>
            <ul>
                <li><span>💸 <strong>Lo Strozzino</strong><br><small>Funding Arb</small></span> <span class="status online">ONLINE</span></li>
                <li><span>📊 <strong>Il Contabile</strong><br><small>DCA Engine</small></span> <span class="status online">ONLINE</span></li>
                <li><span>👼 <strong>L'Angelo Custode</strong><br><small>MEV Arbitrum</small></span> <span class="status online">ONLINE</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="card" style="border-color: #ffaa00; box-shadow: 0 0 15px #ffaa00, inset 0 0 10px #ffaa00;">
            <h3 style="color: #ffaa00; text-shadow: 0 0 10px #ffaa00; border-color: #ffaa00;">🔮 METRICHE DI MERCATO</h3>
            <div class="metric"><span>🧠 <strong>The Oracle</strong> (Sentiment)</span> <span style="color: #0f0; text-shadow: 0 0 5px #0f0;">BULLISH 82%</span></div>
            <div class="metric"><span>🐋 <strong>Whale Tracker</strong> (Inflow)</span> <span style="color: #0ff; text-shadow: 0 0 5px #0ff;">+640 BTC</span></div>
            <div class="metric"><span>🔥 <strong>Volatility Index</strong></span> <span style="color: #f00; text-shadow: 0 0 5px #f00;">ELEVATA</span></div>
            <div class="metric"><span>📡 <strong>Latency</strong> (Nuvola-Binance)</span> <span style="color: #0f0;">8ms</span></div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)
