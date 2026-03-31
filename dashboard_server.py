from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Nuvola Orbital Command</title>
    <style>
        body {
            background-color: #0b0b12;
            color: #00ffcc;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
        }
        h1 {
            text-align: center;
            color: #ff007f;
            text-shadow: 0 0 10px #ff007f, 0 0 20px #ff007f, 0 0 40px #ff007f;
            font-size: 3em;
            margin-bottom: 40px;
            border-bottom: 2px solid #ff007f;
            padding-bottom: 15px;
            letter-spacing: 5px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        .panel {
            border: 1px solid #00ffcc;
            padding: 20px;
            background: rgba(0, 255, 204, 0.03);
            box-shadow: 0 0 20px rgba(0, 255, 204, 0.15) inset, 0 0 10px rgba(0, 255, 204, 0.2);
            border-radius: 8px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, #00ffcc, #ff007f, #ffff00);
            z-index: -1;
            filter: blur(10px);
            opacity: 0.3;
        }
        .panel h2 {
            color: #ffff00;
            text-shadow: 0 0 8px #ffff00;
            border-bottom: 1px dashed #ffff00;
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.5em;
        }
        .status-online {
            color: #00ff00;
            text-shadow: 0 0 8px #00ff00;
            animation: blinker 1.2s cubic-bezier(0.5, 0, 1, 1) infinite alternate;
            font-weight: bold;
        }
        @keyframes blinker {
            from { opacity: 1; }
            to { opacity: 0.3; }
        }
        .item { margin: 15px 0; font-size: 1.2em; display: flex; align-items: center; justify-content: space-between; }
        .item-label { display: flex; align-items: center; }
        .emoji { margin-right: 15px; font-size: 1.4em; }
        .market-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        .market-stat {
            background: rgba(255, 0, 127, 0.05);
            border: 1px solid #ff007f;
            padding: 20px;
            text-align: center;
            box-shadow: 0 0 15px rgba(255, 0, 127, 0.2) inset;
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        .market-stat:hover {
            transform: scale(1.05);
            box-shadow: 0 0 25px rgba(255, 0, 127, 0.4) inset;
        }
        .glitch {
            animation: glitch 2s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); text-shadow: -2px 0 #00ffcc, 2px 2px #ffff00; }
        }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item">
                <span class="item-label"><span class="emoji">🐺</span> SQUADRA_ALPHA [Binance Scalper]</span> 
                <span class="status-online">ENGAGED</span>
            </div>
            <div class="item">
                <span class="item-label"><span class="emoji">🌊</span> SQUADRA_DELTA [Order Flow]</span> 
                <span class="status-online">MONITORING</span>
            </div>
            <div class="item">
                <span class="item-label"><span class="emoji">⚖️</span> SQUADRA_GAMMA [Bitget Pairs]</span> 
                <span class="status-online">SYNCED</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="background: rgba(0, 255, 0, 0.1); border: 1px solid #00ff00; padding: 10px; text-align: center; margin-bottom: 15px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,255,0,0.2);">
                <span class="status-online" style="text-shadow: 0 0 10px #00ff00;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
            </div>
            <div class="item">
                <span class="item-label"><span class="emoji">🦈</span> Lo Strozzino [Funding Arb]</span> 
                <span class="status-online">SYS_BACKGROUND</span>
            </div>
            <div class="item">
                <span class="item-label"><span class="emoji">🧮</span> Il Contabile [DCA]</span> 
                <span class="status-online">SYS_BACKGROUND</span>
            </div>
            <div class="item">
                <span class="item-label"><span class="emoji">🛡️</span> L'Angelo Custode [MEV Arbitrum]</span> 
                <span class="status-online">SYS_BACKGROUND</span>
            </div>
        </div>
        
        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO & INTEL</h2>
            <div class="market-grid">
                <div class="market-stat">
                    <div>🔮 THE ORACLE<br>(Binance Sentiment)</div>
                    <div style="font-size: 1.8em; color: #00ffcc; margin-top: 15px; text-shadow: 0 0 10px #00ffcc;">BULLISH 78%</div>
                </div>
                <div class="market-stat">
                    <div>🐋 WHALE TRACKER<br>(On-Chain Flows)</div>
                    <div style="font-size: 1.8em; color: #ff007f; margin-top: 15px; text-shadow: 0 0 10px #ff007f;">+1.4K BTC</div>
                </div>
                <div class="market-stat">
                    <div>🔥 LIQUIDATION MAP<br>(Heat Zones)</div>
                    <div style="font-size: 1.8em; color: #ffff00; margin-top: 15px; text-shadow: 0 0 10px #ffff00;">SQUEEZE IMMINENT</div>
                </div>
                <div class="market-stat">
                    <div>⚡ NETWORK CONGESTION<br>(Gas Monitor)</div>
                    <div style="font-size: 1.8em; color: #00ff00; margin-top: 15px; text-shadow: 0 0 10px #00ff00;">LOW (12 GWEI)</div>
                </div>
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
