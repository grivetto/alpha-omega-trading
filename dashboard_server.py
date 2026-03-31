import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | SYSTEM OVERVIEW</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #f0ff00;
            --dark-bg: #020202;
            --panel-bg: rgba(5, 10, 5, 0.85);
            --grid-color: rgba(57, 255, 20, 0.1);
        }
        
        * { box-sizing: border-box; }
        
        body {
            background-color: var(--dark-bg);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-green);
        }
        
        h1, h2, h3 {
            margin: 0 0 15px 0;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            font-size: 2.5em;
        }

        h2 {
            font-size: 1.4em;
            border-bottom: 1px solid var(--neon-green);
            padding-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            border: 2px solid var(--neon-cyan);
            box-shadow: 0 0 15px var(--neon-cyan), inset 0 0 15px rgba(0, 255, 255, 0.2);
            background: rgba(0, 20, 20, 0.5);
            position: relative;
        }
        
        .header::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(rgba(0,255,255,0.1) 50%, rgba(0,0,0,0) 50%);
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 10;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
        }
        
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 4px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 20px rgba(57, 255, 20, 0.05);
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: 0 0 15px var(--neon-green), inset 0 0 30px rgba(57, 255, 20, 0.1);
            transform: translateY(-2px);
        }

        .panel.trinity {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        .panel.trinity h2 { border-color: var(--neon-pink); }
        .panel.trinity:hover { box-shadow: 0 0 15px var(--neon-pink); }

        .panel.market {
            border-color: var(--neon-cyan);
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
        }
        .panel.market h2 { border-color: var(--neon-cyan); }
        .panel.market:hover { box-shadow: 0 0 15px var(--neon-cyan); }

        .hud-line {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            margin: 10px 0;
            padding: 5px 0;
            font-size: 1.1em;
        }
        
        .badge {
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
            animation: pulse 2s infinite;
        }

        .badge.active { background: var(--neon-green); color: black; box-shadow: 0 0 10px var(--neon-green); }
        .badge.warning { background: var(--neon-yellow); color: black; box-shadow: 0 0 10px var(--neon-yellow); }
        .badge.danger { background: var(--neon-red); color: white; box-shadow: 0 0 10px var(--neon-red); }
        .badge.shield { background: var(--neon-cyan); color: black; box-shadow: 0 0 10px var(--neon-cyan); }
        .badge.stealth { background: var(--neon-pink); color: white; box-shadow: 0 0 10px var(--neon-pink); }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        .bar-container {
            width: 100%;
            height: 10px;
            background: #111;
            border: 1px solid var(--neon-green);
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }

        .bar-fill {
            height: 100%;
            background: var(--neon-green);
            width: 85%;
            box-shadow: 0 0 10px var(--neon-green);
        }

        .terminal {
            font-family: 'Share Tech Mono', monospace;
            background: #000;
            border: 1px solid var(--neon-cyan);
            padding: 15px;
            height: 180px;
            overflow-y: hidden;
            color: var(--neon-cyan);
            position: relative;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1);
        }
        
        .terminal p { margin: 5px 0; line-height: 1.4; }
        .terminal-cursor {
            display: inline-block;
            width: 10px;
            height: 1.2em;
            background: var(--neon-cyan);
            animation: blink 1s step-end infinite;
            vertical-align: bottom;
        }

        @keyframes blink { 50% { opacity: 0; } }

        .glitch {
            position: relative;
            display: inline-block;
        }

        .grid-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.95em;
        }
        
        .grid-table th, .grid-table td {
            border: 1px solid rgba(0, 255, 255, 0.3);
            padding: 8px;
            text-align: left;
        }
        
        .grid-table th {
            background: rgba(0, 255, 255, 0.1);
            color: var(--neon-cyan);
        }

        .grid-table tr:hover {
            background: rgba(0, 255, 255, 0.05);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p style="font-size: 1.2em; color: var(--neon-green); margin-bottom: 5px;">[ NUVOLA QUANTITATIVE ENGINE // MAIN NODE ]</p>
        <p style="font-size: 1.1em; color: var(--neon-pink); margin-bottom: 5px; font-weight: bold; text-shadow: 0 0 8px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
        <p style="color: #aaa; font-size: 0.9em;">SYSTEM UPTIME: <span id="uptime">99.999%</span> | CLOCK: <span id="clock"></span> | SECURITY: <span style="color: var(--neon-cyan)">MAXIMUM</span></p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="hud-line">
                <div>
                    <strong>🐺 SQUADRA_ALPHA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">&gt; Scalper su Binance</span>
                </div>
                <span class="badge active">ENGAGED</span>
            </div>
            <div class="bar-container"><div class="bar-fill" style="width: 92%; background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red);"></div></div>

            <div class="hud-line">
                <div>
                    <strong>🎯 SQUADRA_DELTA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">&gt; Order Flow / DOM Imbalance</span>
                </div>
                <span class="badge warning">MONITORING</span>
            </div>
            <div class="bar-container"><div class="bar-fill" style="width: 45%; background: var(--neon-yellow);"></div></div>

            <div class="hud-line">
                <div>
                    <strong>⚖️ SQUADRA_GAMMA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">&gt; Pairs Trading su Bitget</span>
                </div>
                <span class="badge active">ARBITRAGE</span>
            </div>
            <div class="bar-container"><div class="bar-fill" style="width: 78%;"></div></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <p style="font-size: 0.85em; margin-bottom: 15px; color: #aaa;">&gt; Core background algorithms online.</p>
            
            <div class="hud-line">
                <div>
                    <strong>🏦 Lo Strozzino</strong><br>
                    <span style="font-size: 0.8em;">[ Funding Arb / Yield Farming ]</span>
                </div>
                <span class="badge stealth">STEALTH</span>
            </div>
            <div class="hud-line">
                <div>
                    <strong>🧮 Il Contabile</strong><br>
                    <span style="font-size: 0.8em;">[ DCA Matrix / Rebalancing ]</span>
                </div>
                <span class="badge active">ACTIVE</span>
            </div>
            <div class="hud-line">
                <div>
                    <strong>👼 L'Angelo Custode</strong><br>
                    <span style="font-size: 0.8em;">[ MEV Arbitrum / Flashbots Shield ]</span>
                </div>
                <span class="badge shield">SHIELDED</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <table class="grid-table">
                <tr>
                    <th>SENSOR</th>
                    <th>DATA FEED</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td>The Oracle</td>
                    <td>Binance Sentiment: 72 (GREED)</td>
                    <td style="color: var(--neon-green)">LONG BIAS</td>
                </tr>
                <tr>
                    <td>Whale Tracker</td>
                    <td>Net Inflow: +8,420 BTC</td>
                    <td style="color: var(--neon-cyan)">ACCUMULATION</td>
                </tr>
                <tr>
                    <td>Liq. Heatmap</td>
                    <td>$450M @ 72,500 USDT</td>
                    <td style="color: var(--neon-red)">MAGNET</td>
                </tr>
                <tr>
                    <td>Funding Rate</td>
                    <td>Avg. +0.0215% (8h)</td>
                    <td style="color: var(--neon-yellow)">ELEVATED</td>
                </tr>
            </table>
        </div>
        
        <!-- TERMINAL FEED -->
        <div class="panel market" style="grid-column: 1 / -1;">
            <h2>💻 LIVE TACTICAL FEED (SECURE STREAM)</h2>
            <div class="terminal" id="terminal-output">
                <p>&gt; Initializing Nuvola Quant Engine... <span style="color: #39ff14">[OK]</span></p>
                <p>&gt; Establishing secure WebSocket to Binance / Bitget... <span style="color: #39ff14">[OK]</span></p>
                <p>&gt; Loading Protocollo Trinity subroutines... <span style="color: #39ff14">[OK]</span></p>
                <p>&gt; SQUADRE D'ASSALTO awaiting engagement vectors...</p>
            </div>
        </div>
    </div>

    <script>
        // Clock update
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }
        setInterval(updateClock, 1000);
        updateClock();

        // Terminal simulation
        const terminal = document.getElementById('terminal-output');
        const lines = [
            "&gt; [ALPHA] Detecting micro-inefficiency on BTC/USDT orderbook. Preparing strike...",
            "&gt; [ALPHA] Flash-fill executed. Profit: +0.012% in 4ms.",
            "&gt; [STROZZINO] Rebalancing perp positions across exchanges. Funding captured.",
            "&gt; [ORACLE] Anomaly detected: Sudden 5000 ETH dump on Bybit. Adjusting risk weights.",
            "&gt; [ANGELO] Shielding transaction from dark forest on Arbitrum. Front-run prevented.",
            "&gt; [GAMMA] Pairs delta deviation exceeded 2.5 sigma. Executing statistical arbitrage.",
            "&gt; [CONTABILE] Scheduled matrix DCA purchase complete. Average entry lowered by 0.4%."
        ];
        
        let termLines = [];
        setInterval(() => {
            const nextLine = lines[Math.floor(Math.random() * lines.length)];
            termLines.push(`<p>${nextLine}</p>`);
            if (termLines.length > 5) termLines.shift();
            
            terminal.innerHTML = termLines.join('') + '<p>&gt; <span class="terminal-cursor"></span></p>';
        }, 2800);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
