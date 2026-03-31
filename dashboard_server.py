import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command ⚡</title>
    <style>
        :root {
            --bg: #050510;
            --text: #00ffcc;
            --glow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
            --alert: #ff0055;
            --alert-glow: 0 0 10px #ff0055, 0 0 20px #ff0055;
            --panel-bg: rgba(0, 255, 204, 0.05);
            --border: 1px solid #00ffcc;
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-x: hidden;
        }
        h1 {
            text-shadow: var(--glow);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--text);
            padding-bottom: 10px;
            animation: flicker 3s infinite alternate;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1400px;
        }
        .panel {
            background: var(--panel-bg);
            border: var(--border);
            padding: 20px;
            border-radius: 5px;
            box-shadow: inset 0 0 10px rgba(0, 255, 204, 0.1);
            position: relative;
        }
        .panel h2 {
            margin-top: 0;
            font-size: 1.2em;
            text-shadow: var(--glow);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .status {
            color: #00ff00;
            font-size: 0.8em;
            animation: blink 1.5s infinite;
        }
        .item {
            margin: 15px 0;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--text);
        }
        .item.alert {
            border-left-color: var(--alert);
            color: var(--alert);
            text-shadow: var(--alert-glow);
        }
        .bar {
            height: 5px;
            background: #111;
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }
        .bar-fill {
            height: 100%;
            background: var(--text);
            box-shadow: var(--glow);
            width: 0%;
            animation: load 2s ease-out forwards;
        }
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .data-box {
            background: rgba(0,0,0,0.8);
            padding: 10px;
            border: 1px dotted var(--text);
            text-align: center;
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: var(--glow); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }
        @keyframes load { to { width: var(--w); } }
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 999;
            opacity: 0.3;
        }
        .radar {
            width: 100%; height: 20px;
            background: repeating-linear-gradient(90deg, transparent, transparent 10px, rgba(0,255,204,0.2) 10px, rgba(0,255,204,0.2) 20px);
            animation: slide 5s linear infinite;
        }
        @keyframes slide { from { background-position: 0 0; } to { background-position: 200px 0; } }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <h1>⚡ Nuvola Orbital Command ⚡</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; text-shadow: var(--glow); color: #00ff00; border: 1px dashed #00ff00; padding: 10px; display: inline-block; animation: blink 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span class="status">[ ONLINE ]</span></h2>
            
            <div class="item">
                <strong>🐺 SQUADRA_ALPHA (Scalper su Binance)</strong>
                <div class="data-grid" style="margin-top:5px;">
                    <div class="data-box">Win Rate<br><span style="color:#00ff00">78.4%</span></div>
                    <div class="data-box">Latency<br>12ms</div>
                </div>
            </div>
            
            <div class="item">
                <strong>🌊 SQUADRA_DELTA (Order Flow)</strong>
                <div class="data-grid" style="margin-top:5px;">
                    <div class="data-box">Volume<br>1.2M USDT</div>
                    <div class="data-box">Imbalance<br><span style="color:#ff0055">Short</span></div>
                </div>
            </div>
            
            <div class="item">
                <strong>⚖️ SQUADRA_GAMMA (Pairs Trading su Bitget)</strong>
                <div class="data-grid" style="margin-top:5px;">
                    <div class="data-box">Spread<br>0.45%</div>
                    <div class="data-box">Z-Score<br>2.14</div>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY <span class="status">[ ACTIVE ]</span></h2>
            
            <div class="item">
                <strong>🕴️ Lo Strozzino (Funding Arb)</strong>
                <div style="font-size:0.8em; margin-top:5px;">Capturing premium across Perps/Spot</div>
                <div class="bar"><div class="bar-fill" style="--w: 85%;"></div></div>
            </div>
            
            <div class="item">
                <strong>🧮 Il Contabile (DCA)</strong>
                <div style="font-size:0.8em; margin-top:5px;">Accumulation Phase: BTC, ETH</div>
                <div class="bar"><div class="bar-fill" style="--w: 60%;"></div></div>
            </div>
            
            <div class="item">
                <strong>👼 L'Angelo Custode (MEV Arbitrum)</strong>
                <div style="font-size:0.8em; margin-top:5px;">Monitoring Mempool / Frontrunning Bots</div>
                <div class="bar"><div class="bar-fill" style="--w: 95%;"></div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO <span class="status" style="color:var(--text)">[ SYNCING ]</span></h2>
            
            <div class="item alert">
                <strong>👁️ The Oracle (Binance Sentiment)</strong>
                <div class="data-grid" style="margin-top:5px;">
                    <div class="data-box" style="border-color:var(--alert)">Fear/Greed<br>72 (GREED)</div>
                    <div class="data-box" style="border-color:var(--alert)">L/S Ratio<br>1.45</div>
                </div>
            </div>
            
            <div class="item">
                <strong>🐋 Whale Tracker</strong>
                <div style="font-size:0.8em; margin-top:5px; font-family:monospace;">
                    > 14:02 UTC: 500 BTC moved to Binance<br>
                    > 14:05 UTC: 12,000 ETH withdrawn from Bybit<br>
                    > 14:10 UTC: 50M USDT minted at Tether Treasury
                </div>
                <div class="radar" style="margin-top:10px;"></div>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 30px; font-size: 0.8em; opacity: 0.5;">
        SYSTEM SECURED // END OF LINE
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
