from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ ORBITAL COMMAND ⚡</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-magenta: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 3s infinite alternate;
        }
        .header h1 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green));
            animation: scanline 4s linear infinite;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status-warning { color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-left: 2px solid var(--neon-green); padding-left: 10px; }
        
        .metric-box {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(57, 255, 20, 0.3);
            margin-bottom: 8px;
            padding-bottom: 5px;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 24%, 55% { opacity: 0.5; }
        }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPLINK: SECURE | ENCRYPTION: AES-256</p>
        <p style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); font-weight: bold; font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    <span class="status-active">▶ ENGAGED</span> | Target: Binance Scalping<br>
                    <small>Latency: 12ms | Win Rate: 68.4% | PnL (24h): +$420.50</small>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    <span class="status-active">▶ ENGAGED</span> | Target: Order Flow<br>
                    <small>Monitoring spoofing & whale walls | Imbalance: 62% B</small>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🦂<br>
                    <span class="status-active">▶ ENGAGED</span> | Target: Bitget Pairs Trading<br>
                    <small>Spread: 0.15% | Z-Score: +2.1 (Mean Reversion)</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-blue);">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>LO STROZZINO</strong> 🧛‍♂️<br>
                    <span class="status-online">● RUNNING IN BACKGROUND</span><br>
                    <small>Task: Funding Arb | APR: 18.2% | Exposure: Hedged</small>
                </li>
                <li>
                    <strong>IL CONTABILE</strong> 🧮<br>
                    <span class="status-online">● RUNNING IN BACKGROUND</span><br>
                    <small>Task: Smart DCA | Accumulating BTC & ETH</small>
                </li>
                <li>
                    <strong>L'ANGELO CUSTODE</strong> 🛡️<br>
                    <span class="status-online">● RUNNING IN BACKGROUND</span><br>
                    <small>Task: MEV Arbitrum | Frontrun Protection: ON</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-magenta);">
            <h2 style="color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta);">📊 THE ORACLE & METRICS</h2>
            <div class="metric-box">
                <span>The Oracle (Sentiment)</span>
                <span class="status-online">GREED (72/100)</span>
            </div>
            <div class="metric-box">
                <span>Whale Tracker</span>
                <span class="status-warning blink">ALERT: 12k BTC MOVED</span>
            </div>
            <div class="metric-box">
                <span>Binance Volatility Index</span>
                <span class="status-active">ELEVATED</span>
            </div>
            <div class="metric-box">
                <span>Global Liquidations (1h)</span>
                <span class="status-warning">$45.2M (Shorts)</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: #888;">
                [Awaiting live datastream injection...]
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Fallback to port 5000 if not specified
    app.run(host='0.0.0.0', port=5000, debug=False)
