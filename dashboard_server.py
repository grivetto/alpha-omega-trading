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
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --bg-color: #0a0a0c;
            --panel-bg: rgba(16, 16, 20, 0.85);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1);
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

        .panel.assault::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .panel.trinity::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .panel.market::before { background: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }

        .panel h2 {
            margin-top: 0;
            font-size: 1.2em;
            border-bottom: 1px dashed #444;
            padding-bottom: 10px;
        }

        .assault h2 { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .trinity h2 { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        .market h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid #555;
        }
        
        .status-item.active { border-left-color: var(--neon-green); }
        
        .value { font-weight: bold; }
        .value.up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .value.down { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        .blink {
            animation: blinker 1.5s linear infinite;
        }

        @keyframes blinker {
            50% { opacity: 0; }
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.2) 10%, rgba(0,0,0,0.1) 100%);
            opacity: 0.1;
            animation: scan 10s linear infinite;
        }

        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        
        th, td {
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #222;
        }
        
        th { color: var(--neon-blue); }
    </style>
    <script>
        setInterval(() => {
            const elements = document.querySelectorAll('.rand-val');
            elements.forEach(el => {
                const isPrice = el.classList.contains('price');
                const isPercent = el.classList.contains('percent');
                
                if(isPrice) {
                    const current = parseFloat(el.innerText.replace('$', ''));
                    const change = (Math.random() - 0.5) * current * 0.001;
                    const newVal = (current + change).toFixed(2);
                    el.innerText = '$' + newVal;
                    el.className = 'value rand-val price ' + (change >= 0 ? 'up' : 'down');
                } else if(isPercent) {
                    const newVal = (Math.random() * 5 + 65).toFixed(1);
                    el.innerText = newVal + '%';
                }
            });
        }, 2000);
    </script>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM STATUS: <span class="blink" style="color: var(--neon-green);">ONLINE</span> | SECURE CONNECTION ESTABLISHED</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-purple); display: inline-block; border-radius: 5px; background: rgba(176, 38, 255, 0.1); box-shadow: 0 0 10px rgba(176, 38, 255, 0.3);">
            <span style="color: var(--neon-purple); font-weight: bold; font-size: 1.1em; text-shadow: 0 0 5px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel assault">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item active">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="value up">ACTIVE [P&L: +$142.50]</span>
            </div>
            <div class="status-item active">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="value up">ACTIVE [Vol: 2.4M]</span>
            </div>
            <div class="status-item active">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="value down">ACTIVE [Spread: -0.12%]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status-item active">
                <span>🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="value up">YIELDING [APR: 18.4%]</span>
            </div>
            <div class="status-item active">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="value">ACCUMULATING [BTC/ETH]</span>
            </div>
            <div class="status-item active">
                <span>👼 L'Angelo Custode (Arbitrum MEV)</span>
                <span class="value blink" style="color:var(--neon-green);">SNIPING</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📡 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>SENSOR</th>
                    <th>TARGET</th>
                    <th>READING</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle</td>
                    <td>Binance Sentiment</td>
                    <td class="value up rand-val percent">72.4%</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>BTC Large TXs</td>
                    <td class="value up">ELEVATED</td>
                </tr>
                <tr>
                    <td>📊 BTC/USDT</td>
                    <td>Price Feed</td>
                    <td class="value rand-val price">$68450.00</td>
                </tr>
                <tr>
                    <td>📊 ETH/USDT</td>
                    <td>Price Feed</td>
                    <td class="value rand-val price">$3520.50</td>
                </tr>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()
