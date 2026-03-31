import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050510;
            --text-color: #00ffcc;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --neon-blue: #00e5ff;
            --neon-purple: #bc13fe;
            --panel-bg: rgba(0, 20, 40, 0.7);
            --border-color: #00ffcc;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 204, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 204, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            animation: pulse 2s infinite;
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
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 204, 0.2), inset 0 0 15px rgba(0, 255, 204, 0.1);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }

        .status {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            font-size: 1.1em;
        }

        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 8px currentColor;
        }

        .status.online .status-indicator {
            background-color: var(--neon-green);
            color: var(--neon-green);
            animation: blink 1.5s infinite;
        }

        .status.standby .status-indicator {
            background-color: #ffaa00;
            color: #ffaa00;
        }

        ul {
            list-style: none;
            padding: 0;
        }

        li {
            margin-bottom: 10px;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-blue);
            transition: all 0.3s;
        }

        li:hover {
            background: rgba(0, 255, 204, 0.1);
            border-left-color: var(--neon-purple);
            transform: translateX(5px);
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.6);
            padding: 15px;
            border: 1px solid rgba(0, 255, 204, 0.3);
            text-align: center;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 5px;
        }

        .value-red {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .value-blue {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .value-purple {
            color: var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
        }

        .value-green {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }

        .glitch-text {
            animation: glitch 1s linear infinite;
            display: inline-block;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
            50% { text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue), 0 0 40px var(--neon-blue); }
            100% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }

        .terminal-output {
            font-family: 'Courier New', Courier, monospace;
            background: #000;
            padding: 15px;
            border: 1px solid #333;
            height: 150px;
            overflow-y: auto;
            color: #ccc;
            font-size: 0.9em;
        }

        .log-line {
            margin: 2px 0;
        }
        
        .log-time { color: #888; }
        .log-info { color: var(--neon-blue); }
        .log-warn { color: #ffaa00; }
        .log-alert { color: var(--neon-red); font-weight: bold; }
        .log-success { color: var(--neon-green); }

    </style>
</head>
<body>

    <h1><span class="glitch-text">🌐 ORBITAL COMMAND</span> // NUVOLA DASHBOARD</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid var(--neon-green); padding: 10px; background: rgba(57, 255, 20, 0.1); color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status online">
                <div class="status-indicator"></div>
                <span>HFT Engine: OPERATIVO</span>
            </div>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🦅<br>
                    <span style="color: #aaa; font-size: 0.9em;">Role: Scalper on Binance | Latency: 12ms</span><br>
                    <span class="value-green">Status: ENGAGED [Searching liquidations]</span>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🐍<br>
                    <span style="color: #aaa; font-size: 0.9em;">Role: Order Flow | Order Book Imbalance</span><br>
                    <span class="value-blue">Status: MONITORING [Spoofing detected]</span>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🐺<br>
                    <span style="color: #aaa; font-size: 0.9em;">Role: Pairs Trading on Bitget | BTC/ETH Spread</span><br>
                    <span class="value-purple">Status: ACTIVE [Spread narrowing]</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status online">
                <div class="status-indicator"></div>
                <span>Background Daemons: SINCRONIZZATI</span>
            </div>
            <ul>
                <li>
                    <strong>LO STROZZINO</strong> 🏦<br>
                    <span style="color: #aaa; font-size: 0.9em;">Strategy: Funding Arb (Spot vs Perp)</span><br>
                    <span class="value-green">Yield: +18.4% APY | Online</span>
                </li>
                <li>
                    <strong>IL CONTABILE</strong> 🧮<br>
                    <span style="color: #aaa; font-size: 0.9em;">Strategy: Smart DCA & Rebalancing</span><br>
                    <span class="value-blue">Next Buy: 14h 22m | Online</span>
                </li>
                <li>
                    <strong>L'ANGELO CUSTODE</strong> 👼<br>
                    <span style="color: #aaa; font-size: 0.9em;">Strategy: MEV Protection & Arbitrum Arb</span><br>
                    <span class="value-purple">Mempool: Scanning | Online</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="status online">
                <div class="status-indicator"></div>
                <span>Data Feeds: ALLACCIATI</span>
            </div>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div>THE ORACLE Sentiment</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>WHALE TRACKER</div>
                    <div class="metric-value value-red">SELL WALL DETECTED</div>
                </div>
                <div class="metric-box">
                    <div>BINANCE VOL (24h)</div>
                    <div class="metric-value value-blue">$42.8B</div>
                </div>
                <div class="metric-box">
                    <div>LIQUIDATIONS (1h)</div>
                    <div class="metric-value value-red">$14.2M</div>
                </div>
            </div>
            
            <h3 style="margin-top: 20px; font-size: 1em;">TERMINAL OUTPUT</h3>
            <div class="terminal-output" id="terminal">
                <div class="log-line"><span class="log-time">[09:37:01]</span> <span class="log-info">[SYS]</span> Initializing Orbital Command...</div>
                <div class="log-line"><span class="log-time">[09:37:02]</span> <span class="log-success">[NET]</span> Connected to Binance WebSocket.</div>
                <div class="log-line"><span class="log-time">[09:37:04]</span> <span class="log-success">[NET]</span> Connected to Bitget API.</div>
                <div class="log-line"><span class="log-time">[09:37:05]</span> <span class="log-info">[TRINITY]</span> Lo Strozzino checking funding rates...</div>
                <div class="log-line"><span class="log-time">[09:37:08]</span> <span class="log-warn">[HFT]</span> Volatility spike detected in ETH/USDT!</div>
                <div class="log-line"><span class="log-time">[09:37:12]</span> <span class="log-alert">[ALPHA]</span> Executed scalp LONG @ $3,450.20</div>
            </div>
        </div>

    </div>

    <script>
        // Fake terminal logs animation
        const terminal = document.getElementById('terminal');
        const logs = [
            '<span class="log-time">[Now]</span> <span class="log-info">[ORACLE]</span> Sentiment analyzing tweets...',
            '<span class="log-time">[Now]</span> <span class="log-success">[ANGELO]</span> Blocked MEV sandwich attack on Arbitrum.',
            '<span class="log-time">[Now]</span> <span class="log-warn">[WHALE]</span> 500 BTC moved to Binance.',
            '<span class="log-time">[Now]</span> <span class="log-info">[GAMMA]</span> Adjusting spread tolerance.',
            '<span class="log-time">[Now]</span> <span class="log-alert">[ALPHA]</span> Position closed. PNL: +$45.20',
        ];

        setInterval(() => {
            const randomLog = logs[Math.floor(Math.random() * logs.length)];
            const timeStr = new Date().toISOString().substring(11, 19);
            const line = document.createElement('div');
            line.className = 'log-line';
            line.innerHTML = randomLog.replace('[Now]', `[${timeStr}]`);
            terminal.appendChild(line);
            terminal.scrollTop = terminal.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
