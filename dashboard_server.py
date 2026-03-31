from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --bg-color: #050510;
            --primary-glow: #0ff;
            --secondary-glow: #f0f;
            --text-main: #e0e0ff;
            --text-muted: #668;
            --alert-color: #f33;
            --success-color: #3f3;
            --panel-bg: rgba(10, 15, 30, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 10px var(--primary-glow);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--primary-glow);
            padding-bottom: 10px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.2);
        }
        .header h1 {
            color: var(--primary-glow);
            font-size: 2.5em;
            animation: pulse 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--primary-glow);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1) inset;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--primary-glow);
            box-shadow: 0 0 10px var(--primary-glow);
        }
        .panel.trinity::before { background: var(--secondary-glow); box-shadow: 0 0 10px var(--secondary-glow); border-color: var(--secondary-glow); }
        .panel.trinity { border-color: var(--secondary-glow); }
        .panel.trinity h2 { text-shadow: 0 0 10px var(--secondary-glow); color: var(--secondary-glow); }
        
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px dashed var(--text-muted);
        }
        .status:last-child { border-bottom: none; }
        .badge-online {
            color: var(--bg-color);
            background: var(--success-color);
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.8em;
            box-shadow: 0 0 8px var(--success-color);
        }
        .badge-active {
            color: var(--bg-color);
            background: var(--primary-glow);
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.8em;
            box-shadow: 0 0 8px var(--primary-glow);
            animation: blink 1s infinite alternate;
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }
        th, td { text-align: left; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: var(--primary-glow); }
        .up { color: var(--success-color); }
        .down { color: var(--alert-color); }

        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--primary-glow); }
            50% { text-shadow: 0 0 25px var(--primary-glow), 0 0 5px #fff; }
            100% { text-shadow: 0 0 10px var(--primary-glow); }
        }
        @keyframes blink {
            from { opacity: 1; }
            to { opacity: 0.5; }
        }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,255,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 8s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND 🌐</h1>
        <p>SYSTEM STATUS: <span style="color:var(--success-color); text-shadow: 0 0 5px var(--success-color);">ONLINE</span> | SECURE CONNECTION ESTABLISHED</p>
        <p style="color:var(--secondary-glow); text-shadow: 0 0 5px var(--secondary-glow); font-weight: bold; font-size: 1.1em; border: 1px solid var(--secondary-glow); display: inline-block; padding: 5px 15px; border-radius: 4px; background: rgba(255, 0, 255, 0.1);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🐺 SQUADRA_ALPHA <span style="font-size:0.8em; color:var(--text-muted);">(Binance Scalper)</span></span>
                <span class="badge-active">DEPLOYED</span>
            </div>
            <div class="status">
                <span>⚡ SQUADRA_DELTA <span style="font-size:0.8em; color:var(--text-muted);">(Order Flow)</span></span>
                <span class="badge-active">ENGAGING</span>
            </div>
            <div class="status">
                <span>⚖️ SQUADRA_GAMMA <span style="font-size:0.8em; color:var(--text-muted);">(Bitget Pairs)</span></span>
                <span class="badge-active">HUNTING</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--primary-glow);">
                > ALPHA: +1.2% PNL (24h) | Latency: 12ms<br>
                > DELTA: Flow imbalance detected (BTC/USDT)<br>
                > GAMMA: Spread 0.45% (ETH/SOL)
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status">
                <span>🎩 Lo Strozzino <span style="font-size:0.8em; color:var(--text-muted);">(Funding Arb)</span></span>
                <span class="badge-online">ONLINE</span>
            </div>
            <div class="status">
                <span>🧮 Il Contabile <span style="font-size:0.8em; color:var(--text-muted);">(DCA Matrix)</span></span>
                <span class="badge-online">ONLINE</span>
            </div>
            <div class="status">
                <span>🛡️ L'Angelo Custode <span style="font-size:0.8em; color:var(--text-muted);">(MEV Arbitrum)</span></span>
                <span class="badge-online">ONLINE</span>
            </div>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--secondary-glow);">
                > STROZZINO: Yield 14.5% APR<br>
                > CONTABILE: Next allocation in 4h 12m<br>
                > CUSTODE: 3 mempool snipes today (0.05 ETH)
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>SOURCE</th>
                    <th>METRIC</th>
                    <th>VALUE</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle</td>
                    <td>Binance Sentiment</td>
                    <td class="up">82.4 (BULLISH)</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>Large Txs (BTC)</td>
                    <td class="up">+450M INFLOW</td>
                </tr>
                <tr>
                    <td>🌐 Liquid. Matrix</td>
                    <td>Orderbook Imbalance</td>
                    <td class="down">-12.5% (SELL BIAS)</td>
                </tr>
                <tr>
                    <td>⚡ Network Load</td>
                    <td>ETH Gas Avg</td>
                    <td class="up">15 Gwei</td>
                </tr>
            </table>
            <div style="margin-top: 15px; font-size: 0.8em; text-align: right; color: var(--text-muted);">
                [ LIVE DATA STREAM ACTIVE ]
            </div>
        </div>
    </div>

    <div style="margin-top: 30px; text-align: center; color: var(--text-muted); font-size: 0.8em;">
        <p>NUVOLA CORE v9.2.1 | NEURAL NET: SYNCHRONIZED | TRADING ENGINE: ARMED</p>
    </div>
    
    <script>
        // Randomize numeric values slightly for the "live" effect
        setInterval(() => {
            const els = document.querySelectorAll('.badge-active');
            els.forEach(el => {
                el.style.opacity = Math.random() > 0.2 ? 1 : 0.5;
            });
        }, 500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
