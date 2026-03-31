from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #00ffcc;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            color: #ff0055;
            text-shadow: 0 0 10px #ff0055, 0 0 20px #ff0055;
            letter-spacing: 2px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            position: relative;
            z-index: 2;
        }
        .panel {
            border: 1px solid #00ffcc;
            padding: 20px;
            box-shadow: 0 0 15px #00ffcc22 inset, 0 0 10px #00ffcc;
            background: rgba(0, 255, 204, 0.05);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: #00ffcc;
            box-shadow: 0 0 10px #00ffcc;
        }
        .panel-title {
            border-bottom: 1px dashed #00ffcc;
            padding-bottom: 10px;
            margin-top: 0;
        }
        .status-online {
            color: #39ff14;
            text-shadow: 0 0 5px #39ff14;
            animation: pulse 2s infinite;
        }
        .status-executing {
            color: #ffaa00;
            text-shadow: 0 0 5px #ffaa00;
        }
        .squad { 
            margin-bottom: 15px; 
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid #ff0055;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .metric-box {
            border: 1px solid #bc13fe;
            padding: 15px;
            text-align: center;
            box-shadow: 0 0 10px #bc13fe55 inset, 0 0 5px #bc13fe;
            background: rgba(188, 19, 254, 0.05);
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: fixed;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,204,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.3;
            animation: scan 6s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100vh; }
        }
        .glitch-text {
            animation: glitch 3s infinite;
        }
        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1 class="glitch-text">⚡ ORBITAL COMMAND TERMINAL ⚡</h1>
    <p>SYSTEM STATUS: <span class="status-online">ENGAGED & FULLY OPERATIONAL</span></p>
    <div style="background: rgba(0, 255, 204, 0.2); border: 1px solid #00ffcc; padding: 10px; margin-bottom: 20px; text-align: center; font-size: 1.2em; text-shadow: 0 0 5px #00ffcc;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="squad">
                <strong>🦅 SQUADRA_ALPHA</strong><br>
                Role: Scalper on Binance<br>
                Status: <span class="status-online">ACTIVE</span> | PnL: <span style="color:#39ff14">+2.45%</span> (24h)
            </div>
            <div class="squad">
                <strong>🌪️ SQUADRA_DELTA</strong><br>
                Role: Order Flow Analysis<br>
                Status: <span class="status-executing">MONITORING L2</span> | Targets: Locked
            </div>
            <div class="squad">
                <strong>☢️ SQUADRA_GAMMA</strong><br>
                Role: Pairs Trading on Bitget<br>
                Status: <span class="status-executing">EXECUTING</span> | Spread: <span id="gamma-spread">0.15</span>%
            </div>
        </div>

        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="squad">
                <strong>💼 Lo Strozzino</strong><br>
                Role: Funding Arbitrage<br>
                Status: <span class="status-online">ONLINE</span> (Background Process PID 4091)
            </div>
            <div class="squad">
                <strong>🧮 Il Contabile</strong><br>
                Role: DCA Management<br>
                Status: <span class="status-online">ONLINE</span> (Background Process PID 4092)
            </div>
            <div class="squad">
                <strong>👼 L'Angelo Custode</strong><br>
                Role: MEV Arbitrum<br>
                Status: <span class="status-online">ONLINE</span> (Background Process PID 4093)
            </div>
        </div>

        <div class="panel" style="grid-column: 1 / -1;">
            <h2 class="panel-title">📡 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <h3 style="color:#bc13fe; text-shadow: 0 0 10px #bc13fe;">👁️ THE ORACLE</h3>
                    <p>Binance Sentiment</p>
                    <p style="font-size: 28px; color: #39ff14; font-weight: bold;" id="oracle-val">BULLISH (72.4%)</p>
                </div>
                <div class="metric-box">
                    <h3 style="color:#bc13fe; text-shadow: 0 0 10px #bc13fe;">🐳 WHALE TRACKER</h3>
                    <p>Large Transactions</p>
                    <p style="font-size: 28px; color: #ff0055; font-weight: bold;" id="whale-val">DETECTED: 4 (>$10M)</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Simulate real-time military UI data changes
        setInterval(() => {
            const spread = (0.10 + Math.random() * 0.10).toFixed(3);
            document.getElementById('gamma-spread').innerText = spread;
            
            if (Math.random() > 0.7) {
                const sentiment = (70 + Math.random() * 10).toFixed(1);
                document.getElementById('oracle-val').innerText = `BULLISH (${sentiment}%)`;
            }
            
            if (Math.random() > 0.8) {
                const whales = Math.floor(Math.random() * 8) + 1;
                document.getElementById('whale-val').innerText = `DETECTED: ${whales} (>$10M)`;
            }
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
