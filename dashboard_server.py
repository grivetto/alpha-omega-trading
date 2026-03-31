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
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            margin-top: 0;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .grid-data {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            font-size: 0.9em;
        }
        .data-box {
            border: 1px dashed rgba(0, 255, 255, 0.5);
            padding: 10px;
            text-align: center;
            background: rgba(0,0,0,0.5);
        }
        .data-value { font-size: 1.5em; font-weight: bold; margin-top: 5px; color: #fff; text-shadow: 0 0 5px #fff; }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        .scanline {
            width: 100%; height: 100px; z-index: 9999; position: absolute; pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,255,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1; animation: scanline 6s linear infinite;
        }
        @keyframes scanline { 0% { top: -100px; } 100% { top: 100%; } }
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding-left: 15px; border-left: 2px solid var(--neon-pink); }
        .header { text-align: center; margin-bottom: 30px; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>NUVOLA TACTICAL QUANTITATIVE DASHBOARD <span class="blink status-online">[SYSTEM ONLINE]</span></p>
        <p style="font-size: 1.2em; border: 1px solid var(--neon-pink); padding: 5px; display: inline-block; color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><strong>SQUADRA_ALPHA</strong> [Scalper @ Binance] <br> <span class="status-active">▶ ENGAGED</span> | Latency: 12ms | PnL: +$145.20</li>
                <li><strong>SQUADRA_DELTA</strong> [Order Flow] <br> <span class="status-online">▶ STANDBY</span> | Scanning Order Books...</li>
                <li><strong>SQUADRA_GAMMA</strong> [Pairs Trading @ Bitget] <br> <span class="status-active">▶ ENGAGED</span> | Target: BTC/ETH Spread | Delta: 0.045</li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p>Background Operations: <span class="status-online">NOMINAL</span></p>
            <ul>
                <li>🕵️ <strong>Lo Strozzino</strong> (Funding Arb)<br> <span class="status-online">▶ ACTIVE</span> | APY: 18.4% | Margin: $12,400</li>
                <li>🧮 <strong>Il Contabile</strong> (DCA Accumulation)<br> <span class="status-online">▶ ACTIVE</span> | Next Buy: 04:00 UTC | Asset: BTC</li>
                <li>👼 <strong>L'Angelo Custode</strong> (MEV @ Arbitrum)<br> <span class="status-online">▶ ACTIVE</span> | Mempool Scanning | Flashbots Connected</li>
            </ul>
        </div>

        <!-- THE ORACLE (Sentiment) -->
        <div class="panel">
            <h2>👁️ THE ORACLE (Sentiment Data)</h2>
            <div class="grid-data">
                <div class="data-box">
                    <div>Fear & Greed</div>
                    <div class="data-value status-active" id="fg-index">74</div>
                </div>
                <div class="data-box">
                    <div>Binance L/S Ratio</div>
                    <div class="data-value" id="ls-ratio">1.45</div>
                </div>
                <div class="data-box">
                    <div>Social Volume</div>
                    <div class="data-value status-online">HIGH</div>
                </div>
            </div>
            <p style="margin-top: 15px; font-size: 0.8em; color: #888;">[Live Feed Intercepted] Predicting local top in 4 hours.</p>
        </div>

        <!-- WHALE TRACKER -->
        <div class="panel">
            <h2>🐋 WHALE TRACKER (On-Chain)</h2>
            <div class="grid-data" style="grid-template-columns: 1fr;">
                <div class="data-box" style="text-align: left;">
                    <div>⚠️ ALERT: 1,500 BTC moved to Coinbase (Tx: 0x8a9f...4b2a)</div>
                    <div style="font-size: 0.8em; color: var(--neon-pink);">Probability of Dump: 68%</div>
                </div>
                <div class="data-box" style="text-align: left;">
                    <div>🟢 ALERT: 50M USDT minted at Tether Treasury</div>
                    <div style="font-size: 0.8em; color: var(--neon-green);">Inflow detected. Bullish divergence.</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Simulate minor data fluctuations for effect
        setInterval(() => {
            const fg = document.getElementById('fg-index');
            const ls = document.getElementById('ls-ratio');
            let currentFg = parseInt(fg.innerText);
            let currentLs = parseFloat(ls.innerText);
            
            fg.innerText = currentFg + (Math.random() > 0.5 ? 1 : -1);
            ls.innerText = (currentLs + (Math.random() * 0.02 - 0.01)).toFixed(2);
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
