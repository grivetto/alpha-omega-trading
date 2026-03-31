from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command - Nuvola</title>
    <style>
        body {
            background-color: #0b0c10;
            color: #45f3ff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
        }

        h1, h2 {
            color: #ff003c;
            text-shadow: 0 0 10px #ff003c, 0 0 20px #ff003c;
            text-transform: uppercase;
            border-bottom: 2px solid #ff003c;
            padding-bottom: 5px;
            margin-bottom: 20px;
            letter-spacing: 2px;
        }

        h2 {
            color: #66fcf1;
            text-shadow: 0 0 8px #66fcf1;
            border-bottom: 1px solid #66fcf1;
            font-size: 1.2rem;
        }

        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(11, 12, 16, 0.8);
            border: 1px solid #45f3ff;
            box-shadow: 0 0 15px rgba(69, 243, 255, 0.2) inset;
            border-radius: 5px;
            padding: 20px;
            flex: 1;
            min-width: 320px;
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(to right, transparent, rgba(69, 243, 255, 0.1), transparent);
            animation: scan 4s linear infinite;
            pointer-events: none;
        }

        @keyframes scan {
            100% { left: 200%; }
        }

        .status-online {
            color: #45f3ff;
            font-weight: bold;
            text-shadow: 0 0 8px #45f3ff;
            animation: pulse 2s infinite;
        }

        .status-active {
            color: #ff003c;
            text-shadow: 0 0 8px #ff003c;
            font-weight: bold;
        }

        .status-bg {
            color: #c5c6c7;
            font-style: italic;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }

        .metric {
            background: #1f2833;
            padding: 15px;
            border-left: 3px solid #66fcf1;
            font-size: 0.9rem;
        }

        .metric-title {
            color: #c5c6c7;
            font-size: 0.8rem;
            text-transform: uppercase;
            margin-bottom: 5px;
            display: block;
        }

        .metric-value {
            font-size: 1.2rem;
            font-weight: bold;
            color: #ffffff;
            text-shadow: 0 0 5px #ffffff;
        }

        .val-bullish { color: #00ff00; text-shadow: 0 0 8px #00ff00; }
        .val-bearish { color: #ff0000; text-shadow: 0 0 8px #ff0000; }
        .val-neutral { color: #ffff00; text-shadow: 0 0 8px #ffff00; }

        .terminal-header {
            margin-bottom: 30px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="terminal-header">
        <h1>[ ⚡ ORBITAL COMMAND ⚡ ]</h1>
        <p>SYSTEM UPLINK: <span class="status-online">SECURE & ONLINE</span> | NUVOLA CORE: <span class="status-active">ACTIVE</span></p>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p>🔴 <b>SQUADRA_ALPHA</b> [Scalper Binance]<br> &nbsp;&nbsp;└─ Status: <span class="status-active">ENGAGED</span> | Latency: 12ms | Orders/sec: 45.2</p>
            <p>🔵 <b>SQUADRA_DELTA</b> [Order Flow]<br> &nbsp;&nbsp;└─ Status: <span class="status-online">WAITING FOR VOLUME</span> | Depth: 250M</p>
            <p>🟣 <b>SQUADRA_GAMMA</b> [Pairs Trading Bitget]<br> &nbsp;&nbsp;└─ Status: <span class="status-active">ENGAGED</span> | Current Spread: 0.18%</p>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; border: 1px solid #66fcf1; background-color: rgba(102, 252, 241, 0.1); color: #66fcf1; font-weight: bold; text-align: center;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <p>🕶️ <b>Lo Strozzino</b> [Funding Arb]<br> &nbsp;&nbsp;└─ State: <span class="status-bg">ONLINE (Background)</span> | Yield: +14% APY</p>
            <p>🧮 <b>Il Contabile</b> [DCA]<br> &nbsp;&nbsp;└─ State: <span class="status-bg">ONLINE (Background)</span> | Next buy in 4h</p>
            <p>👼 <b>L'Angelo Custode</b> [MEV Arbitrum]<br> &nbsp;&nbsp;└─ State: <span class="status-bg">ONLINE (Background)</span> | Tx Saved: 14,021</p>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel" style="flex-basis: 100%;">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="grid">
                <div class="metric">
                    <span class="metric-title">👁️ The Oracle (Binance Sentiment)</span>
                    <span class="metric-value val-bullish">BULLISH (78%)</span>
                </div>
                <div class="metric">
                    <span class="metric-title">🐋 Whale Tracker (On-Chain)</span>
                    <span class="metric-value val-bearish">LARGE SHORT INCOMING</span>
                </div>
                <div class="metric">
                    <span class="metric-title">📈 BTC/USDT Volatility Index</span>
                    <span class="metric-value val-neutral">MODERATE (34.2)</span>
                </div>
                <div class="metric">
                    <span class="metric-title">🌐 ETH Network Congestion</span>
                    <span class="metric-value val-bullish">LOW (12 Gwei)</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

if __name__ == '__main__':
    # Start the server on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
