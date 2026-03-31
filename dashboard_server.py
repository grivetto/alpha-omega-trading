import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --text-color: #e0e0e0;
            --panel-bg: rgba(20, 20, 20, 0.8);
            --border-glow: 0 0 10px;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            animation: pulse-blue 2s infinite alternate;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            padding: 20px;
            border-radius: 5px;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid transparent;
            border-radius: 5px;
            pointer-events: none;
        }

        .panel.hft::before { border-color: var(--neon-red); box-shadow: var(--border-glow) var(--neon-red); animation: border-pulse-red 3s infinite; }
        .panel.trinity::before { border-color: var(--neon-pink); box-shadow: var(--border-glow) var(--neon-pink); animation: border-pulse-pink 4s infinite; }
        .panel.metrics::before { border-color: var(--neon-green); box-shadow: var(--border-glow) var(--neon-green); animation: border-pulse-green 2.5s infinite; }

        .panel-title {
            display: flex;
            align-items: center;
            font-size: 1.2em;
            margin-bottom: 15px;
            border-bottom: 1px dashed #444;
            padding-bottom: 5px;
        }
        
        .hft .panel-title { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .trinity .panel-title { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .metrics .panel-title { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }

        .item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .status {
            font-weight: bold;
            animation: blink 1.5s infinite;
        }

        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status.active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status.standby { color: #fdfd96; text-shadow: 0 0 5px #fdfd96; }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border: 1px solid #222;
            text-align: center;
        }

        .metric-value {
            font-size: 1.5em;
            color: var(--neon-green);
            margin-top: 5px;
            text-shadow: 0 0 5px var(--neon-green);
            font-family: 'Consolas', monospace;
        }

        .log-window {
            margin-top: 20px;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            font-size: 0.9em;
            color: #aaa;
        }

        .log-entry { margin-bottom: 5px; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }

        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes pulse-blue { from { text-shadow: 0 0 10px var(--neon-blue); } to { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); } }
        @keyframes border-pulse-red { 0%, 100% { box-shadow: 0 0 5px var(--neon-red); } 50% { box-shadow: 0 0 15px var(--neon-red); } }
        @keyframes border-pulse-pink { 0%, 100% { box-shadow: 0 0 5px var(--neon-pink); } 50% { box-shadow: 0 0 15px var(--neon-pink); } }
        @keyframes border-pulse-green { 0%, 100% { box-shadow: 0 0 5px var(--neon-green); } 50% { box-shadow: 0 0 15px var(--neon-green); } }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(32,194,14,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline { 0% { top: -100px; } 100% { top: 100vh; } }

    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>NUVOLA TACTICAL DASHBOARD v3.0 - NEURAL LINK ESTABLISHED</p>
        <div style="margin-top: 15px; font-size: 1.2em; color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); animation: blink 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel hft">
            <div class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <div class="item">
                <span>🐺 SQUADRA_ALPHA <br><small>[Scalper / Binance]</small></span>
                <span class="status active">ENGAGING</span>
            </div>
            <div class="item">
                <span>🦅 SQUADRA_DELTA <br><small>[Order Flow / Bybit]</small></span>
                <span class="status online">MONITORING</span>
            </div>
            <div class="item">
                <span>🦂 SQUADRA_GAMMA <br><small>[Pairs Trading / Bitget]</small></span>
                <span class="status active">ARBITRAGING</span>
            </div>
            <div class="log-window" id="hft-logs">
                <div class="log-entry"><span class="log-time">[11:53:01]</span> ALPHA: Executed buy order BTC/USDT @ 98,240</div>
                <div class="log-entry"><span class="log-time">[11:53:05]</span> GAMMA: Spread ETH/BTC detected > 0.4%</div>
                <div class="log-entry"><span class="log-time">[11:53:12]</span> DELTA: Massive volume spike on SOL perp</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <div class="panel-title">👁️‍🗨️ PROTOCOLLO TRINITY</div>
            <div class="item">
                <span>🎩 Lo Strozzino <br><small>[Funding Arb / Cross-Ex]</small></span>
                <span class="status online">YIELDING</span>
            </div>
            <div class="item">
                <span>🧮 Il Contabile <br><small>[Smart DCA / Spot]</small></span>
                <span class="status standby">STANDBY</span>
            </div>
            <div class="item">
                <span>🛡️ L'Angelo Custode <br><small>[MEV / Arbitrum]</small></span>
                <span class="status active">PATROLLING</span>
            </div>
            <div class="log-window" id="trinity-logs">
                <div class="log-entry"><span class="log-time">[11:50:00]</span> Strozzino: Collected 0.015% funding on Bybit</div>
                <div class="log-entry"><span class="log-time">[11:51:22]</span> Angelo: Blocked sandwich attack tx 0x4a...</div>
                <div class="log-entry"><span class="log-time">[11:52:45]</span> Contabile: Next DCA buy window in 4h 12m</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <div class="panel-title">📊 THE ORACLE & WHALE TRACKER</div>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>GLOBAL SENTIMENT</div>
                    <div class="metric-value">GREED (74)</div>
                </div>
                <div class="metric-box">
                    <div>BTC DOMINANCE</div>
                    <div class="metric-value">54.2%</div>
                </div>
                <div class="metric-box">
                    <div>WHALE ACTIVITY</div>
                    <div class="metric-value" style="color: var(--neon-red);">HIGH</div>
                </div>
                <div class="metric-box">
                    <div>LIQUIDITY POOLS</div>
                    <div class="metric-value">STABLE</div>
                </div>
            </div>
            <div class="log-window" id="oracle-logs">
                <div class="log-entry"><span class="log-time">[11:53:10]</span> ORACLE: Binance order book imbalance (Bids +12%)</div>
                <div class="log-entry"><span class="log-time">[11:53:15]</span> WHALE: 1,500 BTC moved to Coinbase</div>
                <div class="log-entry"><span class="log-time">[11:53:20]</span> SYSTEM: Network latency 14ms (OPTIMAL)</div>
            </div>
        </div>

    </div>

    <script>
        const hftLogs = document.getElementById('hft-logs');
        const hftMessages = [
            "ALPHA: Partial fill on limit order.",
            "DELTA: Order flow imbalance shifting.",
            "GAMMA: Rebalancing portfolio weights.",
            "SYSTEM: Latency spike detected and mitigated."
        ];

        setInterval(() => {
            const now = new Date();
            const timeStr = `[${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}]`;
            const msg = hftMessages[Math.floor(Math.random() * hftMessages.length)];
            const div = document.createElement('div');
            div.className = 'log-entry';
            div.innerHTML = `<span class="log-time">${timeStr}</span> ${msg}`;
            hftLogs.appendChild(div);
            hftLogs.scrollTop = hftLogs.scrollHeight;
        }, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
