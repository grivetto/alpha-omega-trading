from flask import Flask, render_template_string
import random
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA TERMINAL</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-yellow: #ff0;
            --neon-red: #f00;
            --bg-color: #020202;
            --panel-bg: rgba(10, 10, 10, 0.85);
            --grid-line: rgba(0, 255, 0, 0.05);
        }

        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        /* CRT Glitch effect */
        body::after {
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
            margin-top: 0;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .glitch-header {
            text-align: center;
            border: 2px solid var(--neon-cyan);
            padding: 20px;
            margin-bottom: 30px;
            background: rgba(0, 255, 255, 0.05);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.2), inset 0 0 10px rgba(0, 255, 255, 0.1);
            position: relative;
        }

        .glitch-header h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            font-size: 2.5em;
            margin-bottom: 5px;
            animation: glitch-anim 5s infinite;
        }

        .glitch-header p {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
            font-size: 1.2em;
            margin: 0;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.1), inset 0 0 15px rgba(0, 255, 0, 0.05);
            position: relative;
            backdrop-filter: blur(4px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 0, 0.3), inset 0 0 20px rgba(0, 255, 0, 0.1);
            transform: translateY(-2px);
        }

        .panel.magenta {
            border-color: var(--neon-magenta);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.1), inset 0 0 15px rgba(255, 0, 255, 0.05);
        }
        .panel.magenta:hover {
            box-shadow: 0 0 25px rgba(255, 0, 255, 0.3), inset 0 0 20px rgba(255, 0, 255, 0.1);
        }

        .panel.cyan {
            border-color: var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1), inset 0 0 15px rgba(0, 255, 255, 0.05);
        }
        .panel.cyan:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.3), inset 0 0 20px rgba(0, 255, 255, 0.1);
        }

        .panel-header {
            border-bottom: 1px dashed currentColor;
            padding-bottom: 10px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel.green .panel-header { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .panel.magenta .panel-header { color: var(--neon-magenta); text-shadow: 0 0 8px var(--neon-magenta); }
        .panel.cyan .panel-header { color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); }

        /* Animated corner brackets */
        .panel::before, .panel::after {
            content: ''; position: absolute; width: 15px; height: 15px; border: 2px solid transparent; transition: all 0.3s ease;
        }
        .panel::before { top: -2px; left: -2px; border-top-color: inherit; border-left-color: inherit; }
        .panel::after { bottom: -2px; right: -2px; border-bottom-color: inherit; border-right-color: inherit; }

        .squad-list { list-style: none; padding: 0; margin: 0; }
        .squad-item { 
            display: flex; flex-direction: column; 
            margin-bottom: 15px; padding: 10px; 
            background: rgba(0, 255, 0, 0.03); 
            border-left: 3px solid var(--neon-green);
            position: relative;
            overflow: hidden;
        }
        .panel.magenta .squad-item { background: rgba(255, 0, 255, 0.03); border-left-color: var(--neon-magenta); }
        .panel.cyan .squad-item { background: rgba(0, 255, 255, 0.03); border-left-color: var(--neon-cyan); }

        .squad-item::before {
            content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            animation: sweep 4s infinite linear;
        }
        
        .squad-item:nth-child(2)::before { animation-delay: 1.5s; }
        .squad-item:nth-child(3)::before { animation-delay: 3s; }

        .squad-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
        .squad-name { font-weight: bold; font-size: 1.1em; letter-spacing: 1px; }
        
        .status { padding: 2px 6px; font-size: 0.8em; font-weight: bold; border: 1px solid; border-radius: 2px; }
        .status.active { color: var(--bg-color); background-color: var(--neon-green); box-shadow: 0 0 8px var(--neon-green); animation: pulse-green 2s infinite; }
        .status.bg-task { color: var(--neon-magenta); border-color: var(--neon-magenta); background: transparent; animation: pulse-magenta 3s infinite; }
        .status.cyan-badge { color: var(--bg-color); background-color: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan); }
        
        .squad-desc { color: #888; font-size: 0.85em; display: flex; justify-content: space-between; }
        .squad-metrics { color: var(--neon-yellow); font-size: 0.9em; margin-top: 5px; text-shadow: 0 0 3px var(--neon-yellow); }

        .chart-placeholder {
            height: 60px;
            margin-top: 10px;
            background: repeating-linear-gradient(90deg, transparent, transparent 10px, rgba(0,255,255,0.1) 10px, rgba(0,255,255,0.1) 11px);
            position: relative;
            border-bottom: 1px solid var(--neon-cyan);
            border-left: 1px solid var(--neon-cyan);
        }
        
        .chart-line {
            position: absolute; bottom: 0; width: 100%; height: 100%;
            background: linear-gradient(45deg, transparent 40%, rgba(0,255,255,0.3) 50%, transparent 60%);
            background-size: 200% 100%;
            animation: dataFlow 3s infinite linear;
            clip-path: polygon(0 100%, 10% 80%, 20% 90%, 30% 50%, 40% 70%, 50% 30%, 60% 60%, 70% 20%, 80% 40%, 90% 10%, 100% 30%, 100% 100%);
            background-color: rgba(0, 255, 255, 0.2);
        }

        .terminal-lines {
            font-size: 0.8em;
            color: #555;
            height: 100px;
            overflow: hidden;
            margin-top: 15px;
            border: 1px solid #333;
            padding: 5px;
            background: #000;
        }

        @keyframes sweep { 0% { left: -100%; } 100% { left: 100%; } }
        @keyframes pulse-green { 0%, 100% { box-shadow: 0 0 5px var(--neon-green); opacity: 1; } 50% { box-shadow: 0 0 15px var(--neon-green); opacity: 0.8; } }
        @keyframes pulse-magenta { 0%, 100% { box-shadow: inset 0 0 2px var(--neon-magenta); opacity: 1; } 50% { box-shadow: inset 0 0 8px var(--neon-magenta); opacity: 0.6; } }
        @keyframes dataFlow { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
        @keyframes glitch-anim {
            0%, 100% { transform: translate(0); }
            10% { transform: translate(-2px, 1px); }
            20% { transform: translate(2px, -1px); }
            30% { transform: translate(-1px, 2px); }
            40% { transform: translate(1px, -2px); }
            50% { transform: translate(-2px, 1px); }
            60% { transform: translate(2px, -1px); }
            70% { transform: translate(-1px, 2px); }
            80% { transform: translate(1px, -2px); }
            90% { transform: translate(-2px, 1px); }
        }

        .blink-text { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <div class="glitch-header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA TERMINAL 🛰️</h1>
        <p>SYSTEM STATUS: <span class="blink-text" style="color:var(--neon-green);">ONLINE</span> | SECURE UPLINK ESTABLISHED | ENCRYPTION: MIL-SPEC AES-256</p>
        <p style="color:var(--neon-yellow); margin-top: 10px; font-weight: bold; text-shadow: 0 0 5px var(--neon-yellow);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid-container">
        <!-- ASSAULT SQUADS -->
        <div class="panel green" style="border-color: var(--neon-green);">
            <div class="panel-header">
                <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
                <span class="status active">DEPLOYED</span>
            </div>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">🐺 SQUADRA_ALPHA</span>
                        <span class="status active">SCALPING</span>
                    </div>
                    <div class="squad-desc">
                        <span>Target: Binance Spot</span>
                        <span>Uptime: {{ uptime }}h</span>
                    </div>
                    <div class="squad-metrics">
                        > Win Rate: {{ alpha_wr }}% | PnL 24h: +{{ alpha_pnl }} USDT
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">🎯 SQUADRA_DELTA</span>
                        <span class="status active">FLOW TACTICS</span>
                    </div>
                    <div class="squad-desc">
                        <span>Target: Order Flow Heatmap</span>
                        <span>Latency: 12ms</span>
                    </div>
                    <div class="squad-metrics">
                        > Imbalance Detected: {{ delta_imb }} BTC | Position: SHORT
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">⚖️ SQUADRA_GAMMA</span>
                        <span class="status active">ARBITRAGE</span>
                    </div>
                    <div class="squad-desc">
                        <span>Target: Bitget Pairs</span>
                        <span>Z-Score: {{ gamma_z }}</span>
                    </div>
                    <div class="squad-metrics">
                        > Active Pair: ETH/BTC | Spread: {{ gamma_spread }} bps
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel magenta">
            <div class="panel-header">
                <h2>🔺 PROTOCOLLO TRINITY</h2>
                <span class="status bg-task">GHOST PROTOCOL</span>
            </div>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">🕴️ Lo Strozzino</span>
                        <span class="status bg-task">WATCHING</span>
                    </div>
                    <div class="squad-desc">
                        <span>Role: Funding Rate Arb</span>
                        <span>Engine: C++ Core</span>
                    </div>
                    <div class="squad-metrics">
                        > Yield APY: {{ strozzino_apy }}% | Max Drawdown: 0.1%
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">🧮 Il Contabile</span>
                        <span class="status bg-task">ACCUMULATING</span>
                    </div>
                    <div class="squad-desc">
                        <span>Role: DCA Sniper</span>
                        <span>Engine: Python Script</span>
                    </div>
                    <div class="squad-metrics">
                        > Next Buy In: {{ contabile_time }}s | Total Bag: {{ contabile_bag }} BTC
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">👼 L'Angelo Custode</span>
                        <span class="status bg-task">SHIELDING</span>
                    </div>
                    <div class="squad-desc">
                        <span>Role: MEV Protection</span>
                        <span>Network: Arbitrum</span>
                    </div>
                    <div class="squad-metrics">
                        > Tx Saved: {{ angelo_tx }} | Slippage Prevented: {{ angelo_slip }} ETH
                    </div>
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel cyan">
            <div class="panel-header">
                <h2>📊 METRICHE DI MERCATO</h2>
                <span class="status cyan-badge">LIVE FEED</span>
            </div>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">👁️ The Oracle</span>
                        <span class="status cyan-badge">{{ oracle_val }}% BULLISH</span>
                    </div>
                    <div class="squad-desc">
                        <span>Binance Sentiment Core</span>
                        <span>AI Confidence: High</span>
                    </div>
                    <div class="chart-placeholder">
                        <div class="chart-line"></div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-top">
                        <span class="squad-name">🐋 Whale Tracker</span>
                        <span class="status cyan-badge">ALERT</span>
                    </div>
                    <div class="squad-desc">
                        <span>24h Flow Imbalance</span>
                        <span>Net Flow: {{ whale_val }} BTC</span>
                    </div>
                    <div class="terminal-lines" id="term-out">
                        [SYS] Hooking mempool...<br>
                        [SYS] Tracking top 100 wallets...<br>
                        [WARN] Large movement detected: 1,500 BTC to Binance<br>
                        [INFO] Awaiting confirmation...<br>
                        [SYS] Recalculating support levels...
                    </div>
                </li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.85em; text-align: center; color: var(--neon-cyan);">
                ⚡ Core Match Engine Latency: <strong class="blink-text">{{ latency }}ms</strong>
            </div>
        </div>
    </div>

    <script>
        // Simple script to animate the terminal lines
        const term = document.getElementById('term-out');
        const logs = [
            "[INFO] Parsing new blocks...",
            "[WARN] Gas spike on ETH mainnet",
            "[SYS] Rebalancing portfolio weights...",
            "[SYS] SQUADRA_ALPHA submitted order",
            "[INFO] Funding rates updated",
            "[WARN] The Oracle adjusted sentiment -2%"
        ];
        
        setInterval(() => {
            const newLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toISOString().substring(11, 19);
            term.innerHTML += `<br>[${time}] ${newLog}`;
            term.scrollTop = term.scrollHeight;
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, 
        uptime=random.randint(120, 450),
        alpha_wr=round(random.uniform(65.5, 82.3), 1),
        alpha_pnl=round(random.uniform(120.5, 450.8), 2),
        delta_imb=round(random.uniform(10.5, 50.2), 1),
        gamma_z=round(random.uniform(2.1, 4.5), 2),
        gamma_spread=random.randint(5, 25),
        strozzino_apy=round(random.uniform(8.5, 15.2), 1),
        contabile_time=random.randint(10, 3600),
        contabile_bag=round(random.uniform(0.1, 1.5), 4),
        angelo_tx=random.randint(150, 400),
        angelo_slip=round(random.uniform(0.05, 0.5), 3),
        oracle_val=random.randint(55, 88),
        whale_val=random.randint(-8500, 8500),
        latency=random.randint(8, 24)
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
