from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        body { background-color: #0d0d0d; color: #00ffcc; font-family: 'Courier New', Courier, monospace; margin: 0; padding: 20px; overflow-x: hidden; }
        h1 { text-align: center; text-shadow: 0 0 10px #00ffcc, 0 0 20px #00ffcc; border-bottom: 2px solid #00ffcc; padding-bottom: 10px; animation: flicker 2s infinite alternate; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .panel { background: rgba(0, 255, 204, 0.05); border: 1px solid #00ffcc; border-radius: 5px; padding: 15px; box-shadow: 0 0 15px rgba(0, 255, 204, 0.2) inset, 0 0 10px rgba(0, 255, 204, 0.5); position: relative; }
        .panel::before { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; box-shadow: 0 0 10px #00ffcc; z-index: -1; opacity: 0.5; }
        .panel h2 { color: #ff00ff; text-shadow: 0 0 8px #ff00ff; margin-top: 0; font-size: 1.2em; border-bottom: 1px dashed #ff00ff; padding-bottom: 5px; }
        .status-online { color: #00ff00; text-shadow: 0 0 5px #00ff00; font-weight: bold; }
        .status-active { color: #ffff00; text-shadow: 0 0 5px #ffff00; animation: pulse 1s infinite alternate; }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 8px; border-left: 2px solid #00ffcc; padding-left: 10px; }
        @keyframes flicker { 0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; } 20%, 24%, 55% { opacity: 0.5; } }
        @keyframes pulse { from { opacity: 0.8; } to { opacity: 1; } }
        .scanline { width: 100%; height: 100px; z-index: 9999; position: absolute; pointer-events: none; background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,204,0.2) 50%, rgba(0,0,0,0) 100%); opacity: 0.1; animation: scan 5s linear infinite; }
        @keyframes scan { 0% { top: -100px; } 100% { top: 100%; } }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA NODE 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid #00ffcc; padding: 10px; border-radius: 5px; background: rgba(0, 255, 204, 0.1);">
        <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
    </div>
    <div class="grid">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>[SQUADRA_ALPHA]</strong> 🦈 Scalper Binance<br>Stato: <span class="status-active">ENGAGED</span> | PnL: +1.24%</li>
                <li><strong>[SQUADRA_DELTA]</strong> 🌊 Order Flow<br>Stato: <span class="status-active">SCANNING</span> | Depth: Ottimo</li>
                <li><strong>[SQUADRA_GAMMA]</strong> ⚖️ Pairs Trading (Bitget)<br>Stato: <span class="status-online">STANDBY</span> | Spread: 0.02%</li>
            </ul>
        </div>
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>[Lo Strozzino]</strong> 🦇 Funding Arb<br>Stato: <span class="status-online">ONLINE</span> | APR: 14.2%</li>
                <li><strong>[Il Contabile]</strong> 🧮 DCA Dinamico<br>Stato: <span class="status-online">ONLINE</span> | Next Buy: 4h 12m</li>
                <li><strong>[L'Angelo Custode]</strong> 👼 MEV Arbitrum<br>Stato: <span class="status-active">HUNTING</span> | Tx Sent: 42</li>
            </ul>
        </div>
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <ul>
                <li><strong>[The Oracle]</strong> 🔮 Binance Sentiment<br>Index: 68 (Greed) | Trend: <span style="color:#00ff00">UP</span></li>
                <li><strong>[Whale Tracker]</strong> 🐋 Movimenti On-Chain<br>Alert: 5000 BTC moved to Binance</li>
                <li><strong>[System Load]</strong> 💻 Nuvola Core<br>CPU: 12% | RAM: 4.2GB | Latency: 12ms</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
