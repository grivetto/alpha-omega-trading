from flask import Flask, render_template_string
import random
import time
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola - Orbital Command</title>
    <style>
        :root {
            --bg: #050505;
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-purple: #b0f;
            --border: 1px solid rgba(0, 255, 0, 0.3);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1, h2 {
            text-align: center;
            text-shadow: 0 0 10px var(--neon-green);
            letter-spacing: 2px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            border: var(--border);
            padding: 15px;
            background: rgba(0, 50, 0, 0.1);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.1) inset;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .title {
            font-weight: bold;
            margin-bottom: 10px;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 1.5s infinite;
        }
        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }
        .status-warning {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        .status-special {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
        }
        .terminal {
            margin-top: 20px;
            border: var(--border);
            padding: 10px;
            height: 150px;
            overflow-y: auto;
            font-size: 0.9em;
            background: rgba(0, 0, 0, 0.8);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2) inset;
        }
        .scan-line {
            width: 100%;
            height: 2px;
            background: rgba(0, 255, 0, 0.5);
            position: fixed;
            top: 0;
            left: 0;
            animation: scan 5s linear infinite;
            z-index: 9999;
            pointer-events: none;
        }
        @keyframes scan {
            0% { top: -10px; }
            100% { top: 100vh; }
        }
        .glow-text {
            color: #fff;
            text-shadow: 0 0 10px #fff, 0 0 20px #fff, 0 0 30px var(--neon-green), 0 0 40px var(--neon-green);
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    <h1 class="glow-text">🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2>[ NUVOLA QUANTITATIVE SYSTEM ]</h2>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <ul>
                <li><span>🐺 SQUADRA_ALPHA [Binance Scalper]</span> <span class="status-active">ENGAGED</span></li>
                <li><span>🦅 SQUADRA_DELTA [Order Flow]</span> <span class="status-active">ENGAGED</span></li>
                <li><span>🦂 SQUADRA_GAMMA [Bitget Pairs]</span> <span class="status-active">ENGAGED</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="title">🔺 PROTOCOLLO TRINITY</div>
            <ul>
                <li style="margin-bottom: 15px; border-bottom: 1px solid var(--neon-green); padding-bottom: 5px;"><span class="status-online glow-text">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></li>
                <li><span>🕴️ Lo Strozzino [Funding Arb]</span> <span class="status-online">ONLINE</span></li>
                <li><span>🧮 Il Contabile [DCA]</span> <span class="status-online">ONLINE</span></li>
                <li><span>🛡️ L'Angelo Custode [MEV Arbitrum]</span> <span class="status-online">ONLINE</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="title">📊 METRICHE DI MERCATO</div>
            <ul>
                <li><span>👁️ The Oracle [Binance Sentiment]</span> <span class="status-special">BULLISH 78%</span></li>
                <li><span>🐋 Whale Tracker [Large TXs]</span> <span class="status-warning">DETECTED</span></li>
                <li><span>⚡ Network Latency</span> <span class="status-online">12ms</span></li>
            </ul>
        </div>
    </div>

    <div class="terminal" id="terminal">
        <div>[SYS] ORBITAL COMMAND INITIALIZED.</div>
        <div>[SYS] SECURE CONNECTION TO NUVOLA ESTABLISHED.</div>
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const logs = [
            "[HFT] SQUADRA_ALPHA executes BUY 1.5 BTC @ 64,230",
            "[TRINITY] Lo Strozzino rebalancing Funding Rates...",
            "[SYS] Whale movement detected on chain: 15,000 ETH",
            "[HFT] SQUADRA_DELTA tracking order flow imbalance...",
            "[SYS] L'Angelo Custode successfully preempted MEV sandwich",
            "[HFT] SQUADRA_GAMMA Pairs trading spread optimal",
            "[ORACLE] Sentiment shifting to neutral-bullish."
        ];
        
        setInterval(() => {
            const log = logs[Math.floor(Math.random() * logs.length)];
            const div = document.createElement('div');
            div.textContent = `> ${log}`;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
