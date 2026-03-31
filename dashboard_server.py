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
            --bg-color: #020202;
            --matrix-green: #00ff41;
            --cyber-blue: #00f3ff;
            --alert-red: #ff003c;
            --neon-purple: #bd00ff;
            --panel-bg: rgba(0, 20, 0, 0.4);
            --border-glow: 0 0 10px var(--matrix-green);
            --font-main: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--matrix-green);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }

        /* Scanline Effect */
        body::after {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: repeating-linear-gradient(
                0deg,
                rgba(0, 0, 0, 0.15),
                rgba(0, 0, 0, 0.15) 1px,
                transparent 1px,
                transparent 2px
            );
            pointer-events: none;
            z-index: 1000;
        }

        .crt-flicker {
            animation: flicker 0.15s infinite;
        }

        @keyframes flicker {
            0% { opacity: 0.95; }
            100% { opacity: 1; }
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            color: var(--cyber-blue);
            text-shadow: 0 0 10px var(--cyber-blue), 0 0 20px var(--cyber-blue);
            margin-bottom: 5px;
            letter-spacing: 5px;
        }

        h2 {
            text-align: center;
            font-size: 1.2em;
            color: var(--matrix-green);
            text-shadow: var(--border-glow);
            margin-top: 0;
            margin-bottom: 30px;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--matrix-green);
            box-shadow: inset 0 0 20px rgba(0, 255, 65, 0.1), 0 0 15px rgba(0, 255, 65, 0.2);
            padding: 20px;
            position: relative;
            backdrop-filter: blur(5px);
            border-radius: 4px;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; height: 3px;
            background: linear-gradient(90deg, transparent, var(--matrix-green), transparent);
            animation: scan-horizontal 3s linear infinite;
        }

        @keyframes scan-horizontal {
            0% { opacity: 0; transform: translateX(-100%); }
            50% { opacity: 1; }
            100% { opacity: 0; transform: translateX(100%); }
        }

        .panel-header {
            font-size: 1.2em;
            font-weight: bold;
            border-bottom: 2px dashed var(--matrix-green);
            padding-bottom: 10px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            text-shadow: 0 0 5px var(--matrix-green);
        }

        ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        li {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(0, 255, 65, 0.2);
            font-size: 0.95em;
        }

        li:last-child {
            border-bottom: none;
        }

        .status-badge {
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
            animation: pulse 2s infinite;
        }

        .status-active {
            border: 1px solid var(--cyber-blue);
            color: var(--cyber-blue);
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.4);
        }

        .status-online {
            border: 1px solid var(--matrix-green);
            color: var(--matrix-green);
            box-shadow: 0 0 10px rgba(0, 255, 65, 0.4);
        }

        .status-warning {
            border: 1px solid var(--alert-red);
            color: var(--alert-red);
            box-shadow: 0 0 10px rgba(255, 0, 60, 0.4);
            animation: pulse-fast 1s infinite;
        }
        
        .status-trinity {
            border: 1px solid var(--neon-purple);
            color: var(--neon-purple);
            box-shadow: 0 0 15px rgba(189, 0, 255, 0.6);
            text-shadow: 0 0 5px var(--neon-purple);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        @keyframes pulse-fast {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .trinity-header {
            text-align: center;
            padding: 10px;
            background: rgba(189, 0, 255, 0.1);
            border: 1px solid var(--neon-purple);
            margin-bottom: 15px;
            color: var(--neon-purple);
            text-shadow: 0 0 10px var(--neon-purple);
            font-weight: bold;
            letter-spacing: 2px;
        }

        .terminal {
            margin: 30px auto;
            max-width: 1400px;
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid var(--matrix-green);
            height: 200px;
            overflow-y: auto;
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(0, 255, 65, 0.1);
            font-size: 0.9em;
        }

        .terminal-line {
            margin-bottom: 5px;
            opacity: 0.9;
        }

        .terminal-line .time {
            color: #888;
            margin-right: 10px;
        }

        .sys-prefix { color: var(--cyber-blue); }
        .hft-prefix { color: var(--alert-red); }
        .trin-prefix { color: var(--neon-purple); }
        
        .value-bar-container {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            position: relative;
        }
        .value-bar {
            height: 100%;
            background: var(--cyber-blue);
            box-shadow: 0 0 5px var(--cyber-blue);
        }
        
        .metric-data {
            display: flex;
            flex-direction: column;
            width: 100%;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            width: 100%;
        }

    </style>
</head>
<body class="crt-flicker">
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2>[ NUVOLA QUANTITATIVE SYSTEM ] // UPLINK SECURE</h2>
    <div style="text-align: center; color: var(--neon-purple); margin-bottom: 20px; font-weight: bold; text-shadow: 0 0 10px var(--neon-purple); font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>

    <div class="dashboard-grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <div class="panel-header">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            <ul>
                <li>
                    <span>🐺 SQUADRA_ALPHA <br><small style="color:#aaa;">[Binance Scalper]</small></span>
                    <span class="status-badge status-active">ENGAGED</span>
                </li>
                <li>
                    <span>🦅 SQUADRA_DELTA <br><small style="color:#aaa;">[Order Flow Imbalance]</small></span>
                    <span class="status-badge status-active">ENGAGED</span>
                </li>
                <li>
                    <span>🦂 SQUADRA_GAMMA <br><small style="color:#aaa;">[Pairs Trading - Bitget]</small></span>
                    <span class="status-badge status-active">ENGAGED</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-purple); box-shadow: inset 0 0 20px rgba(189, 0, 255, 0.1);">
            <div class="panel-header" style="color: var(--neon-purple); border-bottom-color: var(--neon-purple);">🔺 PROTOCOLLO TRINITY</div>
            <div class="trinity-header">SYSTEM TRINITY ACTIVE IN BACKGROUND</div>
            <ul>
                <li>
                    <span>🕴️ LO STROZZINO <br><small style="color:#aaa;">[Funding Rate Arbitrage]</small></span>
                    <span class="status-badge status-trinity">ONLINE</span>
                </li>
                <li>
                    <span>🧮 IL CONTABILE <br><small style="color:#aaa;">[Smart DCA Grid]</small></span>
                    <span class="status-badge status-trinity">ONLINE</span>
                </li>
                <li>
                    <span>🛡️ L'ANGELO CUSTODE <br><small style="color:#aaa;">[MEV Sandwich - Arbitrum]</small></span>
                    <span class="status-badge status-trinity">ONLINE</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-header">📊 METRICHE DI MERCATO</div>
            <ul>
                <li>
                    <div class="metric-data">
                        <div class="metric-row">
                            <span>👁️ THE ORACLE <small>[Binance Sentiment]</small></span>
                            <span class="status-badge status-online">BULLISH 82%</span>
                        </div>
                        <div class="value-bar-container"><div class="value-bar" style="width: 82%; background: var(--matrix-green);"></div></div>
                    </div>
                </li>
                <li>
                    <div class="metric-data">
                        <div class="metric-row">
                            <span>🐋 WHALE TRACKER <small>[Large TXs]</small></span>
                            <span class="status-badge status-warning">DETECTED</span>
                        </div>
                        <div class="value-bar-container"><div class="value-bar" style="width: 95%; background: var(--alert-red);"></div></div>
                    </div>
                </li>
                <li>
                    <div class="metric-data">
                        <div class="metric-row">
                            <span>⚡ NETWORK LATENCY <small>[AWS-Tokyo]</small></span>
                            <span class="status-badge status-online">14ms</span>
                        </div>
                    </div>
                </li>
            </ul>
        </div>
    </div>

    <div class="terminal" id="terminal">
        <div class="terminal-line"><span class="time">[00:00:00]</span> <span class="sys-prefix">[SYS]</span> ORBITAL COMMAND INITIALIZED.</div>
        <div class="terminal-line"><span class="time">[00:00:01]</span> <span class="sys-prefix">[SYS]</span> SECURE CONNECTION TO NUVOLA ESTABLISHED.</div>
        <div class="terminal-line"><span class="time">[00:00:02]</span> <span class="trin-prefix">[TRINITY]</span> PROTOCOLLO TRINITY BACKGROUND DAEMONS SYNCHRONIZED.</div>
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const logs = [
            { type: 'hft', prefix: '[HFT]', text: "SQUADRA_ALPHA executing flash BUY 2.1 BTC @ MKT" },
            { type: 'hft', prefix: '[HFT]', text: "SQUADRA_DELTA detected heavy Ask wall at 71,500. Adjusting..." },
            { type: 'hft', prefix: '[HFT]', text: "SQUADRA_GAMMA Pairs spread deviation optimal > executing arb" },
            { type: 'trin', prefix: '[TRINITY]', text: "Lo Strozzino balancing Funding Rates on Perps" },
            { type: 'trin', prefix: '[TRINITY]', text: "Il Contabile acquired 0.15 BTC (DCA layer 3)" },
            { type: 'trin', prefix: '[TRINITY]', text: "L'Angelo Custode successfully preempted MEV sandwich on SushiSwap" },
            { type: 'sys', prefix: '[ORACLE]', text: "Sentiment shifting. Retail euphoria +12%" },
            { type: 'sys', prefix: '[WHALE]', text: "Alert: 24,000 ETH moved to Coinbase" }
        ];
        
        function getTimestamp() {
            const now = new Date();
            return `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
        }

        setInterval(() => {
            const log = logs[Math.floor(Math.random() * logs.length)];
            const div = document.createElement('div');
            div.className = 'terminal-line';
            
            let prefixClass = 'sys-prefix';
            if(log.type === 'hft') prefixClass = 'hft-prefix';
            if(log.type === 'trin') prefixClass = 'trin-prefix';

            div.innerHTML = `<span class="time">${getTimestamp()}</span> <span class="${prefixClass}">${log.prefix}</span> ${log.text}`;
            terminal.appendChild(div);
            
            if (terminal.childElementCount > 50) {
                terminal.removeChild(terminal.firstChild);
            }
            
            terminal.scrollTop = terminal.scrollHeight;
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
