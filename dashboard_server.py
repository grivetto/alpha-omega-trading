import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-purple: #bc13fe;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-bottom: 10px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 20px;
            margin-bottom: 30px;
            animation: flicker 1.5s infinite alternate;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 15px;
            box-shadow: 0 0 10px var(--neon-blue) inset;
            border-radius: 5px;
        }
        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            animation: blink 1s infinite;
        }
        .status-active {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }
        ul { list-style-type: none; padding: 0; }
        li { margin: 15px 0; font-size: 0.95em; line-height: 1.4; }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .metric-box {
            border: 1px solid var(--neon-purple);
            padding: 15px;
            text-align: center;
            box-shadow: 0 0 5px var(--neon-purple) inset;
            background: #0a0a0a;
        }
        .metric-val {
            font-size: 1.8em;
            font-weight: bold;
            color: #fff;
            text-shadow: 0 0 8px #fff;
            margin: 10px 0;
        }
        
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0% { text-shadow: 0 0 2px var(--neon-green); }
            100% { text-shadow: 0 0 15px var(--neon-green), 0 0 30px var(--neon-green); }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.1) 50%, rgba(0,0,0,0) 100%);
            animation: scan 6s linear infinite;
            top: 0;
            left: 0;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE & ARMED</span> | UPTIME: 99.99% | SECURE CONNECTION</p>
        <p style="color: var(--neon-purple); font-weight: bold; border: 1px dashed var(--neon-purple); display: inline-block; padding: 5px 15px; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>
    
    <div class="container">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>🐺 SQUADRA_ALPHA</strong><br/>
                    Target: Binance (Scalping)<br/>
                    Status: <span class="status-active">[ ENGAGING ]</span><br/>
                    <small style="color: #888">Latency: 12ms | Win Rate: 68.4%</small>
                </li>
                <li><strong>🌊 SQUADRA_DELTA</strong><br/>
                    Target: Global (Order Flow)<br/>
                    Status: <span class="status-active">[ MONITORING ]</span><br/>
                    <small style="color: #888">Imbalance Detected: +450 BTC</small>
                </li>
                <li><strong>⚖️ SQUADRA_GAMMA</strong><br/>
                    Target: Bitget (Pairs Trading)<br/>
                    Status: <span class="status-active">[ ARBITRAGING ]</span><br/>
                    <small style="color: #888">Spread: 0.15% | Exposure: Hedged</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li><strong>🦇 Lo Strozzino</strong><br/>
                    Role: Funding Arb (Perp/Spot)<br/>
                    Status: <span class="status-online">[ ONLINE - BACKGROUND ]</span><br/>
                    <small style="color: #888">Yielding: 18.5% APR</small>
                </li>
                <li><strong>🧮 Il Contabile</strong><br/>
                    Role: Dynamic DCA<br/>
                    Status: <span class="status-online">[ ONLINE - BACKGROUND ]</span><br/>
                    <small style="color: #888">Next Accumulation: 14h 22m</small>
                </li>
                <li><strong>👼 L'Angelo Custode</strong><br/>
                    Role: MEV Arbitrum Protection<br/>
                    Status: <span class="status-online">[ ONLINE - BACKGROUND ]</span><br/>
                    <small style="color: #888">Blocked TXs: 14 | Saved: 0.45 ETH</small>
                </li>
            </ul>
        </div>

        <!-- METRICS -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>👁️ The Oracle (Sentiment)</div>
                    <div class="metric-val" style="color: var(--neon-green)">BULLISH</div>
                    <small style="color: #888">Conf: 88%</small>
                </div>
                <div class="metric-box">
                    <div>🐳 Whale Tracker</div>
                    <div class="metric-val" style="color: var(--neon-purple)">ACCUM</div>
                    <small style="color: #888">+1.2k BTC/24h</small>
                </div>
                <div class="metric-box">
                    <div>⚡ Network Gwei</div>
                    <div class="metric-val" id="gwei-val">14</div>
                    <small style="color: #888">Ethereum L1</small>
                </div>
                <div class="metric-box">
                    <div>🩸 Liquidations</div>
                    <div class="metric-val" style="color: red">$45M</div>
                    <small style="color: #888">Shorts Rekt</small>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Random metric updates to fake activity
        setInterval(() => {
            const gweiEl = document.getElementById('gwei-val');
            if(Math.random() > 0.5) {
                gweiEl.innerText = Math.floor(Math.random() * 5 + 12);
            }
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
