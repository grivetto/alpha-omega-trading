from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        body {
            background-color: #050505;
            color: #0f0;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px #0f0, 0 0 10px #0f0;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        h1 { 
            color: #0ff; 
            text-shadow: 0 0 10px #0ff, 0 0 20px #0ff, 0 0 30px #0ff; 
            text-align: center; 
            border-bottom: 2px solid #0ff; 
            padding-bottom: 15px; 
            margin-bottom: 30px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid #0f0;
            padding: 20px;
            background: rgba(0, 255, 0, 0.03);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2) inset, 0 0 10px rgba(0, 255, 0, 0.1);
            border-radius: 4px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 5px #0f0;
            opacity: 0.3;
            z-index: -1;
            pointer-events: none;
        }
        .status-online { color: #0f0; animation: blink 1.5s infinite; text-shadow: 0 0 5px #0f0; font-weight: bold; }
        .status-standby { color: #ff0; text-shadow: 0 0 5px #ff0; }
        .status-active { color: #f0f; animation: pulse 1s infinite; text-shadow: 0 0 8px #f0f; font-weight: bold; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.02); } 100% { transform: scale(1); } }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin: 15px 0; border-bottom: 1px dashed rgba(0, 255, 0, 0.3); padding-bottom: 10px;}
        li:last-child { border-bottom: none; }
        
        .metric { font-size: 1.3em; font-weight: bold; color: #0ff; text-shadow: 0 0 8px #0ff; }
        .metric-red { color: #f00; text-shadow: 0 0 8px #f00; }
        .metric-green { color: #0f0; text-shadow: 0 0 8px #0f0; }
        
        .trinity-panel { 
            border-color: #f0f; 
            background: rgba(255, 0, 255, 0.03); 
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) inset; 
        }
        .trinity-panel h2 { color: #f0f; text-shadow: 0 0 5px #f0f, 0 0 15px #f0f; border-bottom: 1px solid rgba(255,0,255,0.3); padding-bottom: 5px; }
        
        .assault-panel h2 { color: #ff0; text-shadow: 0 0 5px #ff0, 0 0 15px #ff0; border-bottom: 1px solid rgba(255,255,0,0.3); padding-bottom: 5px; }
        .assault-panel { border-color: #ff0; box-shadow: 0 0 15px rgba(255, 255, 0, 0.2) inset; }

        .terminal-text { font-size: 0.85em; color: #88ff88; display: block; margin-top: 5px; opacity: 0.8; }
        
        .glow-button {
            background: transparent;
            border: 1px solid #0ff;
            color: #0ff;
            padding: 5px 10px;
            cursor: pointer;
            text-transform: uppercase;
            font-family: monospace;
            box-shadow: 0 0 5px #0ff inset;
            transition: all 0.2s;
        }
        .glow-button:hover { background: rgba(0, 255, 255, 0.2); box-shadow: 0 0 10px #0ff; }
        
        #matrix-bg {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -2; opacity: 0.05; pointer-events: none;
        }
    </style>
</head>
<body>
    <canvas id="matrix-bg"></canvas>
    
    <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>
    
    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel assault-panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA ALPHA</strong> (Scalper - Binance) 
                    <span class="status-online">[ENGAGED]</span>
                    <span class="terminal-text">> Latency: <span id="lat-alpha">12</span>ms | Executions: 1,442/hr | PnL: <span class="metric-green">+$412.50</span></span>
                </li>
                <li>
                    <strong>🦅 SQUADRA DELTA</strong> (Order Flow - Bybit) 
                    <span class="status-active">[HUNTING]</span>
                    <span class="terminal-text">> Imbalance detected: +4.2% bid side | Absorbing liquidity...</span>
                </li>
                <li>
                    <strong>🐍 SQUADRA GAMMA</strong> (Pairs Trading - Bitget) 
                    <span class="status-online">[TRACKING]</span>
                    <span class="terminal-text">> BTC/ETH Spread: Z-Score <span id="zscore">+2.14</span> | Exposure: Delta Neutral</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity-panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; margin-bottom: 15px; font-weight: bold; color: #0f0; border: 1px solid #0f0; padding: 5px; box-shadow: 0 0 10px #0f0 inset;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb) 
                    <span class="status-online">[YIELDING]</span>
                    <span class="terminal-text">> Capturing +0.024% on SOL-PERP | Capacity: $50,000 | APY: 34.2%</span>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA Core) 
                    <span class="status-standby">[STANDBY]</span>
                    <span class="terminal-text">> Next accumulation: 4h 12m | Target: BTC @ Spot | Reserves: $12,400</span>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV - Arbitrum) 
                    <span class="status-active">[SCANNING]</span>
                    <span class="terminal-text">> Monitoring mempool... | Flashbots RPC Active | Last payload: +0.015 ETH</span>
                </li>
            </ul>
        </div>

        <!-- THE ORACLE -->
        <div class="panel">
            <h2>🔮 THE ORACLE (METRICS)</h2>
            <ul>
                <li><strong>Binance Sentiment:</strong> <span class="metric">EXTREME GREED (82)</span></li>
                <li><strong>Global CVD (1H):</strong> <span class="metric-green">+$45.2M</span></li>
                <li><strong>Liquidation Heatmap:</strong> Heavy cluster @ <span class="metric-red">$73,400</span></li>
                <li><strong>Volatility Index:</strong> <span class="metric" id="vol">42.1</span> (Rising)</li>
            </ul>
        </div>

        <!-- WHALE TRACKER -->
        <div class="panel">
            <h2>🐋 WHALE TRACKER</h2>
            <ul id="whale-logs">
                <li>🚨 <strong>1,500 BTC</strong> moved to Coinbase Prime (OTC) <span class="terminal-text">Tx: 0x4a9...f1a | 2 mins ago</span></li>
                <li>🚨 <strong>50,000 ETH</strong> withdrawn from Binance <span class="terminal-text">Tx: 0x8b2...c41 | 14 mins ago</span></li>
                <li>⚠️ <strong>Unusual Options:</strong> Deribit Calls $80k Exp. Friday <span class="terminal-text">Volume spike: 4,000 contracts</span></li>
            </ul>
        </div>
        
    </div>

    <script>
        // Matrix effect background
        const canvas = document.getElementById('matrix-bg');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const letters = '01ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        const fontSize = 16;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);
        
        function drawMatrix() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#0F0';
            ctx.font = fontSize + 'px monospace';
            for (let i = 0; i < drops.length; i++) {
                const text = letters[Math.floor(Math.random() * letters.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
                drops[i]++;
            }
        }
        setInterval(drawMatrix, 50);

        // Simulated real-time updates
        setInterval(() => {
            document.getElementById('lat-alpha').innerText = Math.floor(Math.random() * 8) + 10;
            const zscore = (Math.random() * 0.5 + 2.0).toFixed(2);
            document.getElementById('zscore').innerText = "+" + zscore;
            document.getElementById('vol').innerText = (Math.random() * 2 + 41).toFixed(1);
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Start on port 5000 (typical flask) or whatever was used.
    app.run(host='0.0.0.0', port=5000, debug=False)
