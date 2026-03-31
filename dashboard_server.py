from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --bg: #0a0a0c;
            --neon-cyan: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --text-main: #e0e0e0;
            --panel-bg: rgba(10, 20, 30, 0.85);
        }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            font-size: 2.5em;
            letter-spacing: 5px;
            text-transform: uppercase;
            margin-bottom: 40px;
            animation: glitch 2s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-cyan);
            box-shadow: 0 0 10px var(--neon-cyan);
        }
        .panel.pink::before { background: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.green::before { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        
        h2 {
            margin-top: 0;
            font-size: 1.2em;
            border-bottom: 1px dashed #555;
            padding-bottom: 10px;
        }
        .pink h2 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .green h2 { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .cyan h2 { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        
        ul { list-style: none; padding: 0; }
        li { margin-bottom: 15px; font-size: 0.9em; display: flex; justify-content: space-between; align-items: center;}
        
        .status {
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        .status.online { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); }
        .status.active { background: rgba(0, 243, 255, 0.2); color: var(--neon-cyan); border: 1px solid var(--neon-cyan); }
        .status.standby { background: rgba(255, 153, 0, 0.2); color: #ff9900; border: 1px solid #ff9900; }
        
        .metric-box {
            background: rgba(0,0,0,0.5);
            border: 1px solid #333;
            padding: 10px;
            margin-top: 10px;
            text-align: center;
            font-size: 1.1em;
        }
        .metric-value {
            display: block;
            font-size: 1.5em;
            color: var(--neon-green);
            margin-top: 5px;
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green);
        }
        
        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; box-shadow: 0 0 8px currentColor; }
            100% { opacity: 0.8; }
        }
        @keyframes glitch {
            0% { text-shadow: 0 0 10px var(--neon-cyan); }
            98% { text-shadow: 0 0 10px var(--neon-cyan); transform: translate(0); }
            99% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-cyan); transform: translate(-2px, 1px); }
            100% { text-shadow: 0 0 10px var(--neon-cyan); transform: translate(0); }
        }
        
        .scanline {
            width: 100%; height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,243,255,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 6s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1><span style="color:var(--neon-red)">//</span> ORBITAL COMMAND <span style="color:var(--neon-red)">//</span></h1>
    
    <div style="text-align: center; margin: 0 auto 30px auto; padding: 10px 20px; border: 1px solid var(--neon-pink); background: rgba(255, 0, 234, 0.1); color: var(--text-main); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-pink); max-width: fit-content; box-shadow: 0 0 10px rgba(255, 0, 234, 0.3); border-radius: 5px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel cyan">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div>
                        <strong>SQUADRA_ALPHA</strong><br>
                        <span style="color:#aaa; font-size:0.8em">Binance Scalper | freq: 10ms</span>
                    </div>
                    <span class="status active">ENGAGING</span>
                </li>
                <li>
                    <div>
                        <strong>SQUADRA_DELTA</strong><br>
                        <span style="color:#aaa; font-size:0.8em">Order Flow Analysis</span>
                    </div>
                    <span class="status active">MONITORING</span>
                </li>
                <li>
                    <div>
                        <strong>SQUADRA_GAMMA</strong><br>
                        <span style="color:#aaa; font-size:0.8em">Bitget Pairs Trading</span>
                    </div>
                    <span class="status active">ARBITRAGE</span>
                </li>
            </ul>
            <div class="metric-box">
                Alpha PnL (24h)
                <span class="metric-value" id="alpha-pnl">+$1,240.50</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div>
                        <strong>Lo Strozzino</strong> 🧛‍♂️<br>
                        <span style="color:#aaa; font-size:0.8em">Funding Rate Arbitrage</span>
                    </div>
                    <span class="status online">ONLINE</span>
                </li>
                <li>
                    <div>
                        <strong>Il Contabile</strong> 🧮<br>
                        <span style="color:#aaa; font-size:0.8em">Smart DCA Protocol</span>
                    </div>
                    <span class="status online">ONLINE</span>
                </li>
                <li>
                    <div>
                        <strong>L'Angelo Custode</strong> 🛡️<br>
                        <span style="color:#aaa; font-size:0.8em">MEV Arbitrum Protection</span>
                    </div>
                    <span class="status online">ONLINE</span>
                </li>
            </ul>
            <div class="metric-box">
                Trinity Shield Status
                <span class="metric-value" style="color:var(--neon-pink); text-shadow:0 0 5px var(--neon-pink)">100% INTEGRITY</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <div>
                        <strong>The Oracle</strong> 👁️<br>
                        <span style="color:#aaa; font-size:0.8em">Binance Sentiment Index</span>
                    </div>
                    <span class="status active" style="border-color:var(--neon-green); color:var(--neon-green);">EXTREME GREED</span>
                </li>
                <li>
                    <div>
                        <strong>Whale Tracker</strong> 🐋<br>
                        <span style="color:#aaa; font-size:0.8em">On-Chain Flow Anomaly</span>
                    </div>
                    <span class="status standby">SCANNING</span>
                </li>
            </ul>
            <div style="display: flex; gap: 10px;">
                <div class="metric-box" style="flex:1;">
                    BTC Volatility
                    <span class="metric-value" id="btc-vol">4.2%</span>
                </div>
                <div class="metric-box" style="flex:1;">
                    Global Liquidity
                    <span class="metric-value" id="liq-val">$4.2B</span>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Fake real-time updates for effect
        setInterval(() => {
            const pnl = (1200 + Math.random() * 100).toFixed(2);
            document.getElementById('alpha-pnl').innerText = `+$${pnl}`;
            
            if(Math.random() > 0.7) {
                const vol = (4.0 + Math.random()).toFixed(1);
                document.getElementById('btc-vol').innerText = `${vol}%`;
            }
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
