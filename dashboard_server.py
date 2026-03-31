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
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-red: #f00;
            --neon-purple: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(0, 255, 0, 0.05);
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
            text-shadow: 0 0 5px var(--neon-green);
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.2), 0 0 15px rgba(0, 255, 0, 0.1);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }
        .panel h2 {
            font-size: 1.2em;
            margin-top: 0;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 5px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(0, 255, 0, 0.2);
            padding-bottom: 4px;
        }
        .status .label { font-weight: bold; }
        .status .value.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 1.5s infinite; }
        .status .value.offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .status .value.active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .glitch {
            position: relative;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        .metric-box {
            border: 1px solid var(--neon-green);
            padding: 5px;
            text-align: center;
        }
        .metric-box .val {
            font-size: 1.2em;
            color: var(--neon-cyan);
        }
        .log-container {
            margin-top: 20px;
            border: 1px solid var(--neon-green);
            height: 150px;
            overflow-y: hidden;
            background: rgba(0,0,0,0.8);
            padding: 10px;
            font-size: 0.85em;
        }
        .log-line { margin: 2px 0; }
        .log-time { color: var(--neon-cyan); }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND // NUVOLA_SYS 🛰️</h1>
    
    <div class="container">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span class="label">SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="value online">[ ENGAGED ]</span>
            </div>
            <div class="status">
                <span class="label">SQUADRA_DELTA (Order Flow)</span>
                <span class="value online">[ ENGAGED ]</span>
            </div>
            <div class="status">
                <span class="label">SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="value online">[ ENGAGED ]</span>
            </div>
            <div class="log-container" id="hft-logs">
                <div class="log-line"><span class="log-time">[SYS]</span> Alpha: Executed buy @ 64321.5</div>
                <div class="log-line"><span class="log-time">[SYS]</span> Delta: Order book imbalance detected.</div>
                <div class="log-line"><span class="log-time">[SYS]</span> Gamma: Spread widening on BTC/ETH.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="background: rgba(0,255,0,0.2); border: 1px solid var(--neon-green); padding: 5px; text-align: center; margin-bottom: 15px; font-weight: bold; color: var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status">
                <span class="label">Lo Strozzino (Funding Arb)</span>
                <span class="value active">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span class="label">Il Contabile (DCA)</span>
                <span class="value active">[ ONLINE ]</span>
            </div>
            <div class="status">
                <span class="label">L'Angelo Custode (MEV Arb)</span>
                <span class="value active">[ ONLINE ]</span>
            </div>
             <div class="metrics-grid" style="margin-top: 15px;">
                <div class="metric-box">
                    <div>APR Stimato</div>
                    <div class="val">42.8%</div>
                </div>
                <div class="metric-box">
                    <div>Capitale Protetto</div>
                    <div class="val">100%</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="status">
                <span class="label">The Oracle (Binance Sentiment)</span>
                <span class="value active">BULLISH [78%]</span>
            </div>
            <div class="status">
                <span class="label">Whale Tracker</span>
                <span class="value active">DETECTING ANOMALIES</span>
            </div>
            
            <div class="metrics-grid" style="margin-top: 15px;">
                <div class="metric-box">
                    <div>BTC/USDT</div>
                    <div class="val" id="btc-price">64,592.10</div>
                </div>
                <div class="metric-box">
                    <div>ETH/USDT</div>
                    <div class="val" id="eth-price">3,481.50</div>
                </div>
                <div class="metric-box">
                    <div>Global Volatility</div>
                    <div class="val">HIGH</div>
                </div>
                <div class="metric-box">
                    <div>Network Latency</div>
                    <div class="val">12ms</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simulate logs and price updates
        setInterval(() => {
            const btc = document.getElementById('btc-price');
            const currentBtc = parseFloat(btc.innerText.replace(',', ''));
            const newBtc = currentBtc + (Math.random() * 20 - 10);
            btc.innerText = newBtc.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            
            const logs = document.getElementById('hft-logs');
            const msgs = ["Alpha: Scalp filled +0.02%", "Delta: Liquidations mapped", "Gamma: Rebalancing pairs", "SYS: Syncing nodes..."];
            const msg = msgs[Math.floor(Math.random() * msgs.length)];
            const time = new Date().toISOString().substring(11, 19);
            logs.innerHTML = `<div class="log-line"><span class="log-time">[${time}]</span> ${msg}</div>` + logs.innerHTML;
            if(logs.children.length > 8) logs.removeChild(logs.lastChild);
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
