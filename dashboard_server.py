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
        :root {
            --bg: #050505;
            --text: #0f0;
            --alert: #f00;
            --cyan: #0ff;
            --magenta: #f0f;
            --panel-bg: #111;
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
        }
        h1 {
            color: var(--cyan);
            text-shadow: 0 0 10px var(--cyan), 0 0 20px var(--cyan);
            font-size: 2.5em;
            margin-bottom: 30px;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--text);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--text), transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        h2 {
            color: var(--magenta);
            border-bottom: 1px solid var(--magenta);
            padding-bottom: 10px;
            margin-top: 0;
            text-shadow: 0 0 5px var(--magenta);
            font-size: 1.2em;
        }
        ul { list-style: none; padding: 0; }
        li { margin-bottom: 15px; font-size: 0.9em; line-height: 1.4; }
        .status { font-weight: bold; }
        .online { color: var(--text); text-shadow: 0 0 5px var(--text); }
        .standby { color: #ff0; text-shadow: 0 0 5px #ff0; }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        /* Tactical UI elements */
        .metric-box {
            border: 1px solid var(--cyan);
            padding: 10px;
            margin-top: 10px;
            background: rgba(0, 255, 255, 0.05);
        }
        .metric-title { color: var(--cyan); font-size: 0.8em; }
        .metric-value { font-size: 1.5em; color: white; text-shadow: 0 0 5px white; }
    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND 🛰️<br><span style="font-size: 0.4em; color: var(--text);">[ NUVOLA SYSTEM ONLINE ]</span></h1>

    <div style="width: 100%; max-width: 1200px; text-align: center; margin-bottom: 20px; padding: 15px; background: rgba(0,255,0,0.1); border: 1px solid var(--text); box-shadow: 0 0 10px rgba(0,255,0,0.3); border-radius: 5px;">
        <span style="font-size: 1.5em; font-weight: bold; color: var(--text); text-shadow: 0 0 10px var(--text);" class="blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Binance Scalper]<br>
                    Status: <span class="status online blink">🟢 ENGAGED</span><br>
                    Target: BTC/USDT | PnL (24h): <span style="color:var(--text)">+$452.10</span>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow]<br>
                    Status: <span class="status online">🟢 SCANNING</span><br>
                    Target: ETH/USDT | Order Book Imbalance: 68%
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Bitget Pairs]<br>
                    Status: <span class="status standby">🟡 STANDBY</span><br>
                    Target: SOL/AVAX | Awaiting Spread Divergence
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> (Funding Arb)<br>
                    Status: <span class="status online">🟢 ACTIVE (BACKGROUND)</span><br>
                    APR: 18.5% | Exposure: $10k Hedged
                </li>
                <li>
                    <strong>Il Contabile</strong> (DCA)<br>
                    Status: <span class="status online">🟢 ACTIVE (BACKGROUND)</span><br>
                    Next Buy: 14h 22m | Accumulation: BTC, ETH
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Status: <span class="status online blink">🟢 MONITORING MEMPOOL</span><br>
                    Caught today: 0 Tx | Gas: 12 Gwei
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ THE ORACLE & WHALE TRACKER</h2>
            
            <div class="metric-box">
                <span class="metric-title">🧠 BINANCE SENTIMENT (THE ORACLE)</span><br>
                <span class="metric-value">🐂 EXTREME GREED (82/100)</span>
            </div>
            
            <div class="metric-box">
                <span class="metric-title">🐋 WHALE TRACKER ALERT</span><br>
                <span class="metric-value blink" style="color:var(--alert); text-shadow: 0 0 5px var(--alert);">⚠️ 1,200 BTC ➡️ COINBASE</span>
            </div>

            <div class="metric-box">
                <span class="metric-title">🌐 NETWORK LATENCY</span><br>
                <span class="metric-value" style="font-size: 1.2em; color:var(--text);">API: 12ms | WSS: 8ms</span>
            </div>
        </div>
    </div>

    <div style="margin-top: 40px; font-size: 0.8em; color: #555; text-align: center;">
        <p>SYSTEM UPTIME: <span id="uptime">99.99%</span> | ENCRYPTION: AES-256 | TERMINAL LINK SECURE</p>
    </div>
    
    <script>
        setInterval(() => {
            document.getElementById('uptime').innerText = (99.99 - Math.random() * 0.05).toFixed(2) + '%';
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
