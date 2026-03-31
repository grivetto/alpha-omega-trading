from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-pink: #ff00ff;
            --neon-cyan: #0ff;
            --bg-color: #050505;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
            text-shadow: 0 0 2px var(--neon-green);
        }
        .crt::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        h1, h2, h3 { 
            color: var(--neon-cyan); 
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); 
            margin-top: 0;
        }
        h1 { font-size: 2.5em; text-align: center; border-bottom: 2px solid var(--neon-cyan); padding-bottom: 10px; }
        .container { max-width: 1200px; margin: 0 auto; position: relative; z-index: 1; }
        
        .panel {
            border: 1px solid var(--neon-green);
            padding: 20px;
            margin-bottom: 25px;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2), 0 0 15px rgba(57, 255, 20, 0.3);
            background: rgba(0, 20, 0, 0.6);
            position: relative;
        }
        .panel::after {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            border: 1px solid var(--neon-green);
            opacity: 0.5;
            z-index: -1;
        }
        
        .status-online { color: var(--neon-green); animation: blink 1.5s infinite; text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-active { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); animation: pulse 2s infinite; font-weight: bold; }
        .status-warning { color: #ffeb3b; text-shadow: 0 0 8px #ffeb3b; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
        .card {
            border: 1px dashed var(--neon-pink);
            padding: 15px;
            background: rgba(255, 0, 255, 0.05);
            transition: all 0.3s ease;
        }
        .card:hover { box-shadow: 0 0 15px var(--neon-pink); transform: scale(1.02); }
        .card h3 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); border-bottom: 1px dashed var(--neon-pink); padding-bottom: 5px; }
        
        ul.trinity-list { list-style-type: none; padding-left: 0; }
        ul.trinity-list li {
            padding: 10px;
            border-left: 3px solid var(--neon-cyan);
            margin-bottom: 10px;
            background: rgba(0, 255, 255, 0.05);
            display: flex;
            justify-content: space-between;
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid rgba(57, 255, 20, 0.5); padding: 12px; text-align: left; }
        th { background-color: rgba(57, 255, 20, 0.15); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        tr:hover { background-color: rgba(57, 255, 20, 0.1); }
        
        .glitch-text { animation: glitch 3s infinite; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes pulse { 0% { text-shadow: 0 0 5px var(--neon-pink); } 50% { text-shadow: 0 0 20px var(--neon-pink), 0 0 30px var(--neon-pink); } 100% { text-shadow: 0 0 5px var(--neon-pink); } }
        @keyframes glitch { 0%, 100% { transform: translate(0) } 20% { transform: translate(-2px, 1px) } 40% { transform: translate(-1px, -1px) } 60% { transform: translate(2px, 1px) } 80% { transform: translate(1px, -1px) } }
        
        .progress-bar { width: 100%; background-color: #111; border: 1px solid var(--neon-green); height: 10px; margin-top: 5px; }
        .progress-fill { background-color: var(--neon-green); height: 100%; box-shadow: 0 0 10px var(--neon-green); }
    </style>
</head>
<body class="crt">
    <div class="container">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <div style="text-align: center; margin-bottom: 30px; border-bottom: 1px dashed var(--neon-green); padding-bottom: 10px;">
            SYSTEM STATUS: <span class="status-online">ONLINE</span> &nbsp;|&nbsp; 
            UPTIME: <span class="glitch-text">99.999%</span> &nbsp;|&nbsp; 
            DEFENSE SYSTEMS: <span class="status-active">ARMED</span>
            <br><br>
            <span style="color: var(--neon-cyan); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 8px var(--neon-cyan);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>

        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT ALGORITHMS)</h2>
            <div class="grid">
                <div class="card">
                    <h3>🐺 SQUADRA_ALPHA</h3>
                    <p>> ROLE: Micro-Scalping</p>
                    <p>> TARGET: Binance Spot</p>
                    <p>> LATENCY: 12ms</p>
                    <p>> STATUS: <span class="status-active">[ENGAGED]</span></p>
                    <p>> 5M PNL: <span style="color:var(--neon-green)">+0.45% ▲</span></p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 85%; background-color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div></div>
                    <small>THROTTLE: 85%</small>
                </div>
                
                <div class="card">
                    <h3>⚡ SQUADRA_DELTA</h3>
                    <p>> ROLE: Order Flow / Imbalance</p>
                    <p>> TARGET: Cross-Exchange Routing</p>
                    <p>> LATENCY: 24ms</p>
                    <p>> STATUS: <span class="status-active">[ENGAGED]</span></p>
                    <p>> 1M PNL: <span style="color:var(--neon-green)">+0.12% ▲</span></p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 60%; background-color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div></div>
                    <small>THROTTLE: 60%</small>
                </div>
                
                <div class="card">
                    <h3>🎯 SQUADRA_GAMMA</h3>
                    <p>> ROLE: Statistical Pairs Trading</p>
                    <p>> TARGET: Bitget Futures</p>
                    <p>> LATENCY: 45ms</p>
                    <p>> STATUS: <span class="status-active">[ENGAGED]</span></p>
                    <p>> 1H PNL: <span style="color:var(--neon-green)">+1.20% ▲</span></p>
                    <div class="progress-bar"><div class="progress-fill" style="width: 95%; background-color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></div></div>
                    <small>THROTTLE: 95%</small>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY (GHOST OPERATIONS)</h2>
            <ul class="trinity-list">
                <li>
                    <span>🕴️ <b>LO STROZZINO</b> <br><small>Funding Rate Arbitrage Engine</small></span>
                    <span class="status-online">>> BACKGROUND SYNC</span>
                </li>
                <li>
                    <span>🧮 <b>IL CONTABILE</b> <br><small>Dynamic DCA / Accumulation Matrix</small></span>
                    <span class="status-online">>> BACKGROUND SYNC</span>
                </li>
                <li>
                    <span>👼 <b>L'ANGELO CUSTODE</b> <br><small>MEV Protection & Extraction (Arbitrum L2)</small></span>
                    <span class="status-online">>> BACKGROUND SYNC</span>
                </li>
            </ul>
        </div>

        <div class="panel">
            <h2>👁️ THE ORACLE & WHALE TRACKER (LIVE METRICS)</h2>
            <table>
                <thead>
                    <tr>
                        <th>DATA STREAM</th>
                        <th>LIVE VALUE</th>
                        <th>AI INFERENCE</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Binance Global Sentiment</td>
                        <td class="status-warning">EXTREME FEAR (24/100)</td>
                        <td style="color: #ff3333; text-shadow: 0 0 5px #ff3333;">DUMP PROBABILITY: HIGH</td>
                    </tr>
                    <tr>
                        <td>Whale Wallet [0x7A...9C]</td>
                        <td>+4,500 ETH (Inflow)</td>
                        <td class="status-online">ACCUMULATING</td>
                    </tr>
                    <tr>
                        <td>Orderbook Imbalance (BTC/USDT)</td>
                        <td>68% Bids / 32% Asks</td>
                        <td class="status-active">BUY PRESSURE DETECTED</td>
                    </tr>
                    <tr>
                        <td>Arbitrum L2 Mempool Congestion</td>
                        <td>Low (12 Gwei)</td>
                        <td class="status-online">OPTIMAL FOR MEV TXS</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div style="text-align: right; font-size: 0.8em; color: rgba(57, 255, 20, 0.5); margin-top: 10px;">
            > SYS.UPDATE: 2026-03-31 04:15 UTC<br>
            > END OF TRANSMISSION
        </div>
    </div>
    
    <script>
        // Add random small glitches to numbers
        setInterval(() => {
            const elements = document.querySelectorAll('.glitch-text');
            elements.forEach(el => {
                if(Math.random() > 0.8) {
                    const original = el.innerText;
                    el.innerText = (Math.random() * 100).toFixed(3) + '%';
                    setTimeout(() => el.innerText = original, 100);
                }
            });
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    # Start on port 8080 or preferred dashboard port
    app.run(host='0.0.0.0', port=5000)
