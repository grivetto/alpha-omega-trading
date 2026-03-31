from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
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
        h1, h2, h3 {
            text-shadow: 0 0 10px #0f0, 0 0 20px #0f0;
            text-transform: uppercase;
            margin-top: 0;
        }
        .glow-red { color: #f00; text-shadow: 0 0 10px #f00, 0 0 20px #f00; }
        .glow-cyan { color: #0ff; text-shadow: 0 0 10px #0ff, 0 0 20px #0ff; }
        .glow-purple { color: #f0f; text-shadow: 0 0 10px #f0f, 0 0 20px #f0f; }
        .glow-yellow { color: #ff0; text-shadow: 0 0 10px #ff0; }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid #0f0;
            background: rgba(0, 255, 0, 0.05);
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 2px solid transparent;
            background: linear-gradient(45deg, #0f0, transparent) border-box;
            -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: destination-out;
            mask-composite: exclude;
            pointer-events: none;
        }
        .blink { animation: blinker 1.5s linear infinite; }
        .fast-blink { animation: blinker 0.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .metric-box { border: 1px solid rgba(0,255,0,0.5); padding: 15px; text-align: center; background: rgba(0,0,0,0.5); }
        .metric-val { font-size: 1.8em; font-weight: bold; margin-top: 10px; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #0f0; padding: 10px; text-align: left; }
        th { background: rgba(0,255,0,0.2); text-shadow: none; }
        
        .header-bar {
            text-align: center;
            border-bottom: 2px solid #0f0;
            padding-bottom: 10px;
            margin-bottom: 30px;
            position: relative;
        }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.5;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header-bar">
        <h1><span class="glow-cyan">🛰️ NUVOLA ORBITAL COMMAND 🛰️</span></h1>
        <h3 class="blink glow-red">SYSTEM ONLINE // AUTHORIZED ACCESS ONLY // QUANTITATIVE ENGAGEMENT PROTOCOLS ACTIVE</h3>
        <div style="margin-top: 15px; padding: 10px; border: 2px solid #0f0; background: rgba(0,255,0,0.1); display: inline-block; font-weight: bold; font-size: 1.2em;" class="glow-yellow blink">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 class="glow-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>UNIT</th><th>ROLE</th><th>STATUS</th><th>PNL (24h)</th></tr>
                <tr><td>ALPHA 🐺</td><td>Binance Scalper</td><td><span class="glow-cyan fast-blink">ENGAGING</span></td><td><span class="glow-cyan">+1.24%</span></td></tr>
                <tr><td>DELTA 🦅</td><td>Order Flow Arb</td><td><span class="glow-cyan fast-blink">ENGAGING</span></td><td><span class="glow-cyan">+0.89%</span></td></tr>
                <tr><td>GAMMA 🐍</td><td>Bitget Pairs</td><td><span class="glow-cyan fast-blink">ENGAGING</span></td><td><span class="glow-cyan">+2.10%</span></td></tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="glow-purple">🔮 PROTOCOLLO TRINITY</h2>
            <ul style="list-style-type: none; padding-left: 0; line-height: 1.8;">
                <li>🎩 <strong>Lo Strozzino:</strong> Funding Arb <span class="glow-cyan blink">[ONLINE]</span> <span style="float:right; color:#aaa;">Yield: 18% APY</span></li>
                <li>🧮 <strong>Il Contabile:</strong> Dynamic DCA <span class="glow-cyan blink">[ONLINE]</span> <span style="float:right; color:#aaa;">Target: BTC/ETH</span></li>
                <li>🛡️ <strong>L'Angelo Custode:</strong> Arbitrum MEV <span class="glow-cyan blink">[ONLINE]</span> <span style="float:right; color:#aaa;">Guarding Mempool</span></li>
            </ul>
            <div class="metric-box" style="margin-top:15px; border-color:#f0f;">
                <div style="color:#aaa;">TRINITY SYNC RATE</div>
                <div class="metric-val glow-purple blink">99.98%</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div style="font-size:0.8em; color:#aaa;">THE ORACLE (BINANCE SENTIMENT)</div>
                    <div class="metric-val glow-cyan" id="oracle-val">GREED [78]</div>
                </div>
                <div class="metric-box">
                    <div style="font-size:0.8em; color:#aaa;">WHALE TRACKER</div>
                    <div class="metric-val glow-red" id="whale-val">INFLOW 520 BTC</div>
                </div>
                <div class="metric-box">
                    <div style="font-size:0.8em; color:#aaa;">GLOBAL LIQUIDITY (EST)</div>
                    <div class="metric-val glow-yellow">$1.42T</div>
                </div>
                <div class="metric-box">
                    <div style="font-size:0.8em; color:#aaa;">ORDERBOOK IMBALANCE</div>
                    <div class="metric-val glow-purple">BID BIASED ⚠️</div>
                </div>
            </div>
        </div>

        <!-- SYSTEM LOGS -->
        <div class="panel">
            <h2>📡 SYSTEM LOGS</h2>
            <div id="logs" style="height: 200px; overflow-y: hidden; font-size: 0.9em; color:#aaa; font-family: monospace;">
                [18:15:02] SQUADRA_ALPHA executed 50ms scalp on BTC/USDT.<br>
                [18:15:10] L'Angelo Custode bypassed frontrunner on Arbitrum.<br>
                [18:15:22] Lo Strozzino collected 0.01% funding fee.<br>
                [18:16:05] Whale Tracker: Large stablecoin mint detected.<br>
                [18:16:40] The Oracle: Sentiment shifting to extreme greed.<br>
                <span class="blink">_</span>
            </div>
        </div>
    </div>
    
    <script>
        const logs = [
            "SQUADRA_GAMMA balancing BTC/ETH pair exposure.",
            "Il Contabile executing micro-buy of 0.0025 BTC.",
            "SQUADRA_DELTA analyzing order book imbalance on Binance.",
            "Mempool congestion detected. Adjusting gas for MEV.",
            "Funding rates skewed. Lo Strozzino deploying capital.",
            "Whale Tracker: Outflow of 1,200 ETH from Coinbase.",
            "The Oracle: Minor bearish divergence detected on 1m chart.",
            "L'Angelo Custode executing sandwich defense."
        ];
        
        setInterval(() => {
            const logDiv = document.getElementById('logs');
            const time = new Date().toTimeString().split(' ')[0];
            const newLog = `[${time}] ${logs[Math.floor(Math.random() * logs.length)]}<br>`;
            const currentLogs = logDiv.innerHTML.replace('<span class="blink">_</span>', '').split('<br>').filter(l => l.trim() !== '');
            currentLogs.unshift(`[${time}] ${logs[Math.floor(Math.random() * logs.length)]}`);
            if(currentLogs.length > 8) currentLogs.pop();
            logDiv.innerHTML = currentLogs.join('<br>') + '<br><span class="blink">_</span>';
            
            // Randomize Oracle and Whale Tracker
            if(Math.random() > 0.7) {
                document.getElementById('oracle-val').innerText = `GREED [${Math.floor(70 + Math.random() * 20)}]`;
                document.getElementById('whale-val').innerText = `INFLOW ${Math.floor(100 + Math.random() * 900)} BTC`;
            }
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on default port 5000, visible to all interfaces if needed
    app.run(host='0.0.0.0', port=5000)
