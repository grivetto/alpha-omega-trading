import os
import threading
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #050505;
            --panel-bg: #0a0f12;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --text-main: #e0e0e0;
            --font-mono: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-mono);
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px currentColor;
            margin-top: 0;
        }
        h1 { color: var(--neon-blue); text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px;}
        h2 { color: var(--neon-pink); border-bottom: 1px dashed var(--neon-pink); padding-bottom: 5px; }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid #333;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 5px currentColor;
        }
        .online { background-color: var(--neon-green); color: var(--neon-green); animation: blink 1.5s infinite; }
        .active { background-color: var(--neon-blue); color: var(--neon-blue); animation: blink 2s infinite; }
        .warning { background-color: var(--neon-red); color: var(--neon-red); animation: blink 0.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #222; padding-bottom: 5px;}
        .metric-value { color: var(--neon-green); font-weight: bold; }
        
        .ticker {
            font-size: 1.2em;
            color: var(--neon-green);
        }
    </style>
</head>
<body>
    <h1>🌐 NUVOLA ORBITAL COMMAND 🌐</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-weight: bold; color: var(--neon-green); font-size: 1.2em; border: 1px solid var(--neon-green); padding: 10px; border-radius: 5px; background-color: rgba(57, 255, 20, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <!-- ASSAULT TEAMS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div><span class="status-dot online"></span> SQUADRA_ALPHA</div>
                    <div style="font-size: 0.8em; color: #888;">[Binance Scalper]</div>
                    <div class="metric-value">OP: ACTIVE</div>
                </li>
                <li>
                    <div><span class="status-dot online"></span> SQUADRA_DELTA</div>
                    <div style="font-size: 0.8em; color: #888;">[Order Flow]</div>
                    <div class="metric-value">OP: ACTIVE</div>
                </li>
                <li>
                    <div><span class="status-dot online"></span> SQUADRA_GAMMA</div>
                    <div style="font-size: 0.8em; color: #888;">[Bitget Pairs]</div>
                    <div class="metric-value">OP: ACTIVE</div>
                </li>
            </ul>
        </div>

        <!-- TRINITY PROTOCOL -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div><span class="status-dot active"></span> LO STROZZINO</div>
                    <div style="font-size: 0.8em; color: #888;">[Funding Arb]</div>
                    <div class="metric-value" style="color: var(--neon-blue);">YIELD: 12.4% APR</div>
                </li>
                <li>
                    <div><span class="status-dot active"></span> IL CONTABILE</div>
                    <div style="font-size: 0.8em; color: #888;">[DCA Matrix]</div>
                    <div class="metric-value" style="color: var(--neon-blue);">ACCUMULATING</div>
                </li>
                <li>
                    <div><span class="status-dot active"></span> L'ANGELO CUSTODE</div>
                    <div style="font-size: 0.8em; color: #888;">[MEV Arbitrum]</div>
                    <div class="metric-value" style="color: var(--neon-blue);">WATCHING MEMPOOL</div>
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <div>🔮 THE ORACLE</div>
                    <div style="font-size: 0.8em; color: #888;">[Binance Sentiment]</div>
                    <div class="metric-value" style="color: var(--neon-green);">BULLISH (82%)</div>
                </li>
                <li>
                    <div>🐋 WHALE TRACKER</div>
                    <div style="font-size: 0.8em; color: #888;">[On-Chain Alerts]</div>
                    <div class="metric-value" style="color: var(--neon-red);">ELEVATED</div>
                </li>
                <li>
                    <div>📈 BTC/USDT Ticker</div>
                    <div id="btc-price" class="ticker">68,450.00</div>
                </li>
            </ul>
        </div>
    </div>

    <script>
        // Fake price ticker for ambiance
        let btcPrice = 68450.00;
        setInterval(() => {
            const change = (Math.random() - 0.5) * 10;
            btcPrice += change;
            const el = document.getElementById('btc-price');
            el.innerText = btcPrice.toFixed(2);
            el.style.color = change >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
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
