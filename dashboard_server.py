from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #0f0;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: #0ff;
            text-shadow: 0 0 10px #0ff, 0 0 20px #0ff;
            letter-spacing: 5px;
            border-bottom: 2px solid #0ff;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: rgba(0, 20, 0, 0.8);
            border: 1px solid #0f0;
            box-shadow: 0 0 10px #0f0 inset, 0 0 5px #0f0;
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel h2 {
            margin-top: 0;
            color: #f0f;
            text-shadow: 0 0 5px #f0f;
            border-bottom: 1px dashed #f0f;
            padding-bottom: 5px;
            font-size: 1.2em;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .online { background-color: #0f0; box-shadow: 0 0 8px #0f0; animation: blink 1.5s infinite; }
        .scanning { background-color: #0ff; box-shadow: 0 0 8px #0ff; animation: blink 0.5s infinite; }
        .standby { background-color: #ff0; box-shadow: 0 0 8px #ff0; }
        
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            border-bottom: 1px solid #030;
            padding-bottom: 4px;
        }
        .metric { color: #fff; text-shadow: 0 0 3px #fff; }
        .scan-line {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: rgba(0, 255, 0, 0.5);
            box-shadow: 0 0 10px #0f0;
            animation: scan 3s linear infinite;
        }
        @keyframes scan {
            0% { top: 0; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
        .glitch {
            animation: glitch 2s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>
    <h1 class="glitch">🌐 NUVOLA ORBITAL COMMAND 🌐</h1>
    
    <div style="text-align: center; margin-bottom: 30px; border: 1px solid #0f0; padding: 10px; background: rgba(0, 50, 0, 0.5); font-size: 1.5em; text-shadow: 0 0 5px #0f0; box-shadow: 0 0 10px #0f0;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <div class="scan-line"></div>
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span><span class="status-indicator online"></span> SQUADRA_ALPHA</span>
                <span class="metric">Binance Scalper | APY: +42.5%</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator online"></span> SQUADRA_DELTA</span>
                <span class="metric">Order Flow | APY: +18.2%</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator standby"></span> SQUADRA_GAMMA</span>
                <span class="metric">Bitget Pairs | APY: +22.1%</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="scan-line"></div>
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span><span class="status-indicator online"></span> Lo Strozzino</span>
                <span class="metric">Funding Arb | BACKGROUND</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator online"></span> Il Contabile</span>
                <span class="metric">DCA Engine | BACKGROUND</span>
            </div>
            <div class="data-row">
                <span><span class="status-indicator scanning"></span> L'Angelo Custode</span>
                <span class="metric">MEV Arbitrum | SCANNING...</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="scan-line"></div>
            <h2>👁️ THE ORACLE & WHALE TRACKER</h2>
            <div class="data-row">
                <span>🧠 Oracle Sentiment</span>
                <span class="metric" style="color: #0f0;">EXTREME GREED (78)</span>
            </div>
            <div class="data-row">
                <span>🐋 Whale Alerts</span>
                <span class="metric" style="color: #f00;">🚨 5000 BTC -> BINANCE</span>
            </div>
            <div class="data-row">
                <span>📊 Orderbook Imbalance</span>
                <span class="metric">+5.2% BUY</span>
            </div>
            <div class="data-row">
                <span>⚡ Network Gas (ETH)</span>
                <span class="metric" id="gas-metric">12 Gwei</span>
            </div>
        </div>
    </div>

    <script>
        setInterval(() => {
            const gas = Math.floor(Math.random() * 20 + 10);
            document.getElementById('gas-metric').innerText = gas + ' Gwei';
            document.getElementById('gas-metric').style.color = gas > 25 ? '#f00' : '#fff';
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
