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
            --neon-green: #00ff9d;
            --neon-blue: #00e5ff;
            --neon-red: #ff003c;
            --neon-purple: #b800ff;
            --bg-dark: #0a0a0f;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 157, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 157, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .glow-text-green { text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); }
        .glow-text-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); }
        .glow-text-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red), 0 0 10px var(--neon-red); }
        
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 10px -10px var(--neon-green);
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 15px;
            border-radius: 5px;
            box-shadow: inset 0 0 10px rgba(0,255,157,0.1), 0 0 15px rgba(0,255,157,0.2);
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .trinity-panel { border-color: var(--neon-purple); }
        .trinity-panel::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .trinity-panel h2 { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }

        .market-panel { border-color: var(--neon-blue); }
        .market-panel::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        
        ul { list-style-type: none; padding: 0; }
        li {
            margin-bottom: 10px;
            border-bottom: 1px dashed rgba(0, 255, 157, 0.3);
            padding-bottom: 5px;
            display: flex;
            justify-content: space-between;
        }
        
        .status-online { color: var(--neon-green); animation: blink 1.5s infinite; }
        .status-active { color: var(--neon-blue); animation: blink 2s infinite; }
        .status-warning { color: var(--neon-red); animation: blink 1s infinite; }

        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100vh); }
        }
        
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 50px;
            background: linear-gradient(to bottom, transparent, rgba(0,255,157,0.2), transparent);
            opacity: 0.3;
            pointer-events: none;
            animation: scanline 4s linear infinite;
            z-index: 9999;
        }
        
        .stat-value {
            font-weight: bold;
            font-size: 1.1em;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1 class="glow-text-green">🛰️ ORBITAL COMMAND // NUVOLA_OS v3.0</h1>
        <p>CLASSIFIED QUANTITATIVE INTERFACE // SYSTEM ONLINE // <span id="clock" class="glow-text-blue"></span></p>
        <h3 style="color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); margin-top: 15px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span><strong class="glow-text-red">SQUADRA_ALPHA</strong> (Scalper/Binance)</span>
                    <span class="status-online">[ ENGAGED ]</span>
                </li>
                <li>
                    <span>> Win Rate / PnL Oggi:</span>
                    <span class="stat-value glow-text-green" id="alpha-pnl">68.4% / +$420.50</span>
                </li>
                <li>
                    <span><strong class="glow-text-blue">SQUADRA_DELTA</strong> (Order Flow)</span>
                    <span class="status-active">[ STANDBY ]</span>
                </li>
                <li>
                    <span>> Imbalance Det.:</span>
                    <span class="stat-value">Awaiting Ticks...</span>
                </li>
                <li>
                    <span><strong style="color:#ffcc00">SQUADRA_GAMMA</strong> (Pairs/Bitget)</span>
                    <span class="status-online">[ ENGAGED ]</span>
                </li>
                <li>
                    <span>> Z-Score (BTC/ETH):</span>
                    <span class="stat-value glow-text-red" id="gamma-z">2.41 (SHORT SPREAD)</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span>🕴️ <strong>Lo Strozzino</strong> (Funding Arb)</span>
                    <span class="status-online">[ HARVESTING ]</span>
                </li>
                <li>
                    <span>> Avg APR:</span>
                    <span class="stat-value">18.4%</span>
                </li>
                <li>
                    <span>🧮 <strong>Il Contabile</strong> (DCA)</span>
                    <span class="status-online">[ ACCUMULATING ]</span>
                </li>
                <li>
                    <span>> Next BTC Buy In:</span>
                    <span class="stat-value" id="contabile-timer">04:12:00</span>
                </li>
                <li>
                    <span>🛡️ <strong>L'Angelo Custode</strong> (MEV Arbitrum)</span>
                    <span class="status-online">[ PATROLLING ]</span>
                </li>
                <li>
                    <span>> Mempool Scans/sec:</span>
                    <span class="stat-value glow-text-blue" id="angelo-scans">142</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market-panel">
            <h2 class="glow-text-blue">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <span>👁️ <strong>The Oracle</strong> (Binance Sentiment)</span>
                    <span class="status-active">[ READING ]</span>
                </li>
                <li>
                    <span>> Fear/Greed Index:</span>
                    <span class="stat-value" style="color:#ffcc00">62 (GREED)</span>
                </li>
                <li>
                    <span>> Orderbook Skew:</span>
                    <span class="stat-value glow-text-green">+14.2% BIDS</span>
                </li>
                <li>
                    <span>🐋 <strong>Whale Tracker</strong></span>
                    <span class="status-warning">[ ALERT ACTIVE ]</span>
                </li>
                <li>
                    <span>> Last Big Tx:</span>
                    <span class="stat-value">1,200 BTC -> Coinbase</span>
                </li>
                <li>
                    <span>> Stablecoin Inflow (24h):</span>
                    <span class="stat-value glow-text-green">+$450M</span>
                </li>
            </ul>
        </div>
    </div>

    <script>
        // Fake dynamic updates to make it look alive
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }, 1000);

        setInterval(() => {
            const scans = Math.floor(Math.random() * 50) + 120;
            document.getElementById('angelo-scans').innerText = scans;
        }, 800);

        setInterval(() => {
            const z = (Math.random() * 0.5 + 2.0).toFixed(2);
            document.getElementById('gamma-z').innerText = z + " (SHORT SPREAD)";
        }, 3000);
        
        setInterval(() => {
            const current = document.getElementById('contabile-timer').innerText.split(':');
            let h = parseInt(current[0]), m = parseInt(current[1]), s = parseInt(current[2]);
            s--;
            if(s < 0) { s = 59; m--; }
            if(m < 0) { m = 59; h--; }
            document.getElementById('contabile-timer').innerText = 
                String(h).padStart(2, '0') + ':' + 
                String(m).padStart(2, '0') + ':' + 
                String(s).padStart(2, '0');
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
