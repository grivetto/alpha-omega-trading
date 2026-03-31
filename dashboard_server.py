import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --panel-bg: rgba(0, 20, 40, 0.6);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 15px var(--neon-blue);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 10px -10px var(--neon-blue);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 15px;
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); font-weight: bold; }
        .status-warning { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; border-bottom: 1px dashed rgba(0,243,255,0.3); padding-bottom: 5px; }
        
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { border: 1px solid rgba(0,243,255,0.3); padding: 10px; text-align: center; }
        .metric-value { font-size: 1.5em; color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p class="blink status-online">🟢 UPLINK ESTABLISHED | ENCRYPTION: LEVEL-9 QUANTUM | SYSTEM: ACTIVE</p>
        <p class="status-active">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- ASSAULT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong> [Scalper Binance]<br>
                    Status: <span class="status-active">ENGAGED</span> | Target: BTC/USDT<br>
                    Win Rate: 68% | Latency: 12ms
                </li>
                <li>
                    <strong>👁️ SQUADRA_DELTA</strong> [Order Flow]<br>
                    Status: <span class="status-active">MONITORING</span> | Target: ETH/USDT<br>
                    Imbalance: +14.2% (BULLISH)
                </li>
                <li>
                    <strong>⚖️ SQUADRA_GAMMA</strong> [Pairs Trading Bitget]<br>
                    Status: <span class="status-active">ARBITRAGING</span> | Target: SOL/USDT vs SOL/USDC<br>
                    Spread: 0.04% | Executions: 142/h
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <p>Background Daemons <span class="status-online">ONLINE</span></p>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                    <span class="status-online">✔ ACTIVE</span> - Yield: +18.4% APY (Cross-exchange)
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA Core)<br>
                    <span class="status-online">✔ ACTIVE</span> - Next Accumulation: 04:22:10
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    <span class="status-online">✔ ACTIVE</span> - Mempool Sniffing... (Captured: 0.14 ETH)
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO (THE ORACLE)</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>Fear & Greed</div>
                    <div class="metric-value">72</div>
                    <div class="status-online">GREED</div>
                </div>
                <div class="metric-box">
                    <div>Binance Sentiment</div>
                    <div class="metric-value status-active">BULLISH</div>
                    <div>Long/Short: 1.45</div>
                </div>
                <div class="metric-box">
                    <div>Whale Tracker</div>
                    <div class="metric-value status-warning">ALERT</div>
                    <div>+5000 BTC Moved</div>
                </div>
                <div class="metric-box">
                    <div>Global Volatility</div>
                    <div class="metric-value">14.2%</div>
                    <div class="status-online">STABLE</div>
                </div>
            </div>
            <p style="margin-top: 15px; text-align: center; font-size: 0.8em; opacity: 0.7;">
                Data Feed: <span class="status-online">LIVE</span> (Lag: 4ms)
            </p>
        </div>
    </div>
    
    <script>
        // Fake dynamic updates for realism
        setInterval(() => {
            const values = document.querySelectorAll('.metric-value');
            if (Math.random() > 0.7) {
                // slightly tweak fear/greed
                let fg = parseInt(values[0].innerText);
                fg += (Math.random() > 0.5 ? 1 : -1);
                values[0].innerText = fg;
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000
    app.run(host='0.0.0.0', port=5000)
