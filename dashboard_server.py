import flask
import random
import time

app = flask.Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-main: #00ffcc;
            --text-glow: 0 0 10px #00ffcc, 0 0 20px #00ffcc;
            --alert-color: #ff0055;
            --alert-glow: 0 0 10px #ff0055, 0 0 20px #ff0055;
            --panel-bg: rgba(0, 255, 204, 0.05);
            --border-color: #00ffcc;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        h1 {
            text-align: center;
            font-size: 2.5rem;
            text-shadow: var(--text-glow);
            letter-spacing: 5px;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 204, 0.2);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(0, 255, 204, 0.2), transparent);
            transform: skewX(-20deg);
            animation: scan 5s infinite;
        }

        @keyframes scan {
            0% { left: -100%; }
            50% { left: 200%; }
            100% { left: 200%; }
        }

        h2 {
            font-size: 1.2rem;
            margin-top: 0;
            border-bottom: 1px dashed var(--border-color);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }

        li {
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }

        .status-online {
            color: #00ffcc;
            text-shadow: var(--text-glow);
            animation: pulse 2s infinite;
        }

        .status-active {
            color: #ffff00;
            text-shadow: 0 0 10px #ffff00;
        }

        .status-alert {
            color: var(--alert-color);
            text-shadow: var(--alert-glow);
            animation: blink 1s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        .metric-value {
            font-weight: bold;
        }
        
        .footer {
            margin-top: 50px;
            text-align: center;
            font-size: 0.8rem;
            opacity: 0.7;
        }
        
        /* CRT Effect */
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
    </style>
</head>
<body class="crt">

    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>

    <div style="text-align: center; font-size: 1.2rem; font-weight: bold; margin-bottom: 20px; color: #ffff00; text-shadow: 0 0 10px #ffff00; border: 1px dashed #00ffcc; padding: 10px; display: inline-block; margin-left: 50%; transform: translateX(-50%);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>SQUADRA_ALPHA (Scalper Binance)</span> <span class="status-active metric-value">ENGAGED [245 ops/min]</span></li>
                <li><span>SQUADRA_DELTA (Order Flow)</span> <span class="status-online metric-value">STANDBY [Monitoring]</span></li>
                <li><span>SQUADRA_GAMMA (Pairs Bitget)</span> <span class="status-active metric-value">ARBITRAGE [Spread 0.4%]</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>Lo Strozzino (Funding Arb)</span> <span class="status-online metric-value">ONLINE [Yield 18% APY]</span></li>
                <li><span>Il Contabile (DCA)</span> <span class="status-online metric-value">ONLINE [Next Buy: 4h]</span></li>
                <li><span>L'Angelo Custode (MEV Arb)</span> <span class="status-online metric-value">PROTECTING [0 frontruns]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 THE ORACLE & WHALE TRACKER</h2>
            <ul>
                <li><span>BTC Sentiment (Oracle)</span> <span class="status-active metric-value">BULLISH 78%</span></li>
                <li><span>Whale Netflow (24h)</span> <span class="metric-value" style="color: #00ffcc;">+ $450M</span></li>
                <li><span>Global Liquidity Index</span> <span class="metric-value">RISING 📈</span></li>
                <li><span>System Latency</span> <span class="status-online metric-value">12ms</span></li>
            </ul>
        </div>

    </div>

    <div class="footer">
        <p>SYSTEM STATUS: NOMINAL. SECURE CONNECTION ESTABLISHED. ALL PROTOCOLS ACTIVE.</p>
        <p>TIME: <span id="clock"></span></p>
    </div>

    <script>
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }, 1000);
        // Randomize some values for effect
        setInterval(() => {
            const ops = document.querySelector('.status-active.metric-value');
            if(ops && ops.innerText.includes('ENGAGED')) {
                const newOps = 200 + Math.floor(Math.random() * 100);
                ops.innerText = `ENGAGED [${newOps} ops/min]`;
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return HTML_TEMPLATE

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
