from flask import Flask, render_template_string
import threading
import time

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
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff003c;
            --neon-purple: #bc13fe;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(circle at 50% 50%, #111 0%, #000 100%);
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 3s infinite alternate;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green) inset, 0 0 15px var(--neon-green);
            padding: 15px;
            border-radius: 5px;
        }
        .panel.blue {
            border-color: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue) inset, 0 0 15px var(--neon-blue);
            color: var(--neon-blue);
        }
        .panel.blue h2 { text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); }
        .panel.red {
            border-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red) inset, 0 0 15px var(--neon-red);
            color: var(--neon-red);
        }
        .panel.red h2 { text-shadow: 0 0 5px var(--neon-red), 0 0 10px var(--neon-red); }
        .panel.purple {
            border-color: var(--neon-purple);
            box-shadow: 0 0 10px var(--neon-purple) inset, 0 0 15px var(--neon-purple);
            color: var(--neon-purple);
        }
        .panel.purple h2 { text-shadow: 0 0 5px var(--neon-purple), 0 0 10px var(--neon-purple); }
        
        .status {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid;
        }
        .status.online { border-left-color: var(--neon-green); }
        .status.active { border-left-color: var(--neon-blue); }
        .status.warning { border-left-color: var(--neon-red); }
        
        .blink { animation: blinker 1s linear infinite; }
        
        @keyframes blinker {
            50% { opacity: 0; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 22%, 24%, 55% { opacity: 0.5; }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #333; padding: 5px; text-align: left; }
        th { color: #fff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>
        <p>SYSTEM STATUS: <span class="blink" style="color: var(--neon-green);">ONLINE</span> | SECURE CONNECTION ESTABLISHED</p>
        <p style="color: var(--neon-purple); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel blue">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active">
                <span>🐺 SQUADRA_ALPHA</span>
                <span>[Scalper su Binance] - ENGAGED</span>
            </div>
            <div class="status active">
                <span>⚡ SQUADRA_DELTA</span>
                <span>[Order Flow] - MONITORING</span>
            </div>
            <div class="status active">
                <span>⚖️ SQUADRA_GAMMA</span>
                <span>[Pairs Trading Bitget] - ARBITRATING</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status online">
                <span>🕴️ Lo Strozzino</span>
                <span>[Funding Arb] - ONLINE</span>
            </div>
            <div class="status online">
                <span>🧮 Il Contabile</span>
                <span>[DCA Engine] - ONLINE</span>
            </div>
            <div class="status online">
                <span>🛡️ L'Angelo Custode</span>
                <span>[MEV Arbitrum] - PROTECTING</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel red">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p>👁️ <strong>The Oracle</strong> (Binance Sentiment): <span class="blink">BULLISH 78%</span></p>
            <p>🐋 <strong>Whale Tracker</strong>: <span style="color: var(--neon-red);">LARGE OUTFLOW DETECTED</span></p>
            <table>
                <tr><th>ASSET</th><th>PRICE</th><th>SIGNAL</th></tr>
                <tr><td>BTC/USDT</td><td>$69,420.00</td><td>LONG</td></tr>
                <tr><td>ETH/USDT</td><td>$3,850.50</td><td>HOLD</td></tr>
                <tr><td>SOL/USDT</td><td>$145.20</td><td>SHORT</td></tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
