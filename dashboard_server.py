import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA NETWORK</title>
    <style>
        :root {
            --primary: #0ff;
            --secondary: #f0f;
            --alert: #f00;
            --bg: #0a0a0a;
            --panel: rgba(0, 255, 255, 0.05);
            --border: rgba(0, 255, 255, 0.2);
        }
        
        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }

        body {
            background-color: var(--bg);
            color: var(--primary);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        .crt::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--primary);
            padding-bottom: 20px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--primary);
            animation: flicker 4s infinite;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            z-index: 1;
            position: relative;
        }

        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.05), 0 0 15px rgba(0, 255, 255, 0.1);
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 30px rgba(0, 255, 255, 0.1), 0 0 25px rgba(0, 255, 255, 0.3);
            border-color: var(--primary);
        }

        h2 {
            font-size: 1.2rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
            margin-top: 0;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }

        .status {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--primary);
        }

        .status.active { border-left-color: #0f0; color: #0f0; text-shadow: 0 0 5px #0f0; }
        .status.warning { border-left-color: #ff0; color: #ff0; text-shadow: 0 0 5px #ff0; }
        .status.standby { border-left-color: #555; color: #aaa; }

        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }

        .blink { animation: blink 1.5s infinite; }
        .fast-blink { animation: blink 0.5s infinite; }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: .99; text-shadow: 0 0 10px var(--primary); }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; text-shadow: none; }
        }

        .progress-bar {
            height: 4px;
            background: #333;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--primary);
            box-shadow: 0 0 10px var(--primary);
        }

        .terminal {
            font-family: monospace;
            font-size: 0.8rem;
            color: #0f0;
            height: 150px;
            overflow-y: hidden;
            background: rgba(0, 20, 0, 0.8);
            padding: 10px;
            border: 1px solid #0f0;
            margin-top: 20px;
            text-shadow: 0 0 2px #0f0;
        }
    </style>
</head>
<body class="crt">
    <div class="header">
        <h1>[ TERMINAL UPLINK ] ORBITAL COMMAND</h1>
        <p class="blink">SYSTEM ONLINE // SECURE CONNECTION ESTABLISHED</p>
        <h3 style="color: #0f0; text-shadow: 0 0 10px #0f0;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status active">
                <span>[ ALPHA ] Scalper (Binance)</span>
                <span class="fast-blink">ENGAGED</span>
            </div>
            <div class="metric"><span>Win Rate:</span><span>78.4%</span></div>
            <div class="metric"><span>Trades/min:</span><span>142</span></div>
            
            <div class="status active">
                <span>[ DELTA ] Order Flow</span>
                <span class="blink">SCANNING</span>
            </div>
            <div class="metric"><span>Liquidity Pools:</span><span>Tracking</span></div>
            <div class="metric"><span>Spoofing Detect:</span><span>Active</span></div>

            <div class="status warning">
                <span>[ GAMMA ] Pairs Trading (Bitget)</span>
                <span>REBALANCING</span>
            </div>
            <div class="metric"><span>Spread:</span><span>0.15%</span></div>
            <div class="metric"><span>Exposure:</span><span>Neutral</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status active">
                <span>💰 Lo Strozzino (Funding Arb)</span>
                <span>HARVESTING</span>
            </div>
            <div class="metric"><span>Current Yield:</span><span>28.4% APR</span></div>
            <div class="progress-bar"><div class="progress-fill" style="width: 85%"></div></div>
            
            <div class="status active">
                <span>📊 Il Contabile (DCA)</span>
                <span>ACCUMULATING</span>
            </div>
            <div class="metric"><span>Next Buy:</span><span>T-14:02:45</span></div>
            <div class="progress-bar"><div class="progress-fill" style="width: 40%; background: #0f0; box-shadow: 0 0 10px #0f0;"></div></div>

            <div class="status active">
                <span>👼 L'Angelo Custode (MEV)</span>
                <span>MONITORING</span>
            </div>
            <div class="metric"><span>Network:</span><span>Arbitrum One</span></div>
            <div class="metric"><span>Frontrun Protect:</span><span>Maximized</span></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>🌐 METRICHE GLOBALI</h2>
            <div class="status active">
                <span>👁️ The Oracle (Sentiment)</span>
                <span class="blink">BULLISH</span>
            </div>
            <div class="metric"><span>Fear & Greed:</span><span style="color: #0f0">74</span></div>
            <div class="metric"><span>Social Volume:</span><span>+14.2%</span></div>

            <div class="status warning">
                <span>🐋 Whale Tracker</span>
                <span class="fast-blink">ALERT</span>
            </div>
            <div class="metric"><span>Large Tx:</span><span>Inflow 5000 BTC</span></div>
            <div class="metric"><span>Exchange Res:</span><span>Spike Detected</span></div>
            
            <div class="terminal">
                > Initializing quant models... OK<br>
                > Connecting to Binance WebSocket... OK<br>
                > Connecting to Arbitrum RPC... OK<br>
                > Analyzing orderbook depth... [████████░░] 80%<br>
                > ALERT: Volatility spike detected on ETH/USDT<br>
                > SQUADRA ALPHA redeploying capital...<br>
                > _
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
