from flask import Flask

app = Flask(__name__)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-base: #020202;
            --grid-color: rgba(0, 255, 170, 0.05);
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-pink: #ff007f;
            --neon-yellow: #fcee0a;
            --neon-red: #ff003c;
            --text-main: #d1d1d1;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Share Tech Mono', monospace;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        /* Scanline Overlay */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        header {
            text-align: center;
            padding: 30px 0 20px 0;
            border-bottom: 2px solid var(--neon-cyan);
            box-shadow: 0 4px 15px rgba(0, 255, 255, 0.2);
            margin-bottom: 40px;
            position: relative;
        }

        h1 {
            color: var(--neon-cyan);
            font-size: 3.5rem;
            text-transform: uppercase;
            letter-spacing: 5px;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan);
            margin-bottom: 10px;
            animation: glitch 3s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0 0 10px var(--neon-cyan); }
            2% { transform: translate(-2px, 2px); text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-cyan); }
            4% { transform: translate(2px, -2px); text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-cyan); }
            6% { transform: translate(0, 0); text-shadow: 0 0 10px var(--neon-cyan); }
            100% { text-shadow: 0 0 10px var(--neon-cyan); }
        }

        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border: 1px solid var(--neon-green);
            color: var(--neon-green);
            background: rgba(57, 255, 20, 0.1);
            border-radius: 3px;
            text-shadow: 0 0 5px var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            animation: pulse-green 2s infinite;
        }

        @keyframes pulse-green {
            0% { box-shadow: 0 0 5px var(--neon-green); }
            50% { box-shadow: 0 0 20px var(--neon-green); }
            100% { box-shadow: 0 0 5px var(--neon-green); }
        }

        .dashboard-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            padding: 0 40px 40px 40px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: rgba(10, 10, 15, 0.85);
            border: 1px solid #333;
            padding: 25px;
            border-radius: 5px;
            position: relative;
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }

        .panel:hover {
            transform: translateY(-5px);
        }

        .panel-hft {
            border-top: 3px solid var(--neon-pink);
            box-shadow: 0 -5px 15px rgba(255, 0, 127, 0.2), inset 0 0 20px rgba(255, 0, 127, 0.05);
        }

        .panel-trinity {
            border-top: 3px solid var(--neon-cyan);
            box-shadow: 0 -5px 15px rgba(0, 255, 255, 0.2), inset 0 0 20px rgba(0, 255, 255, 0.05);
        }

        .panel-market {
            grid-column: 1 / -1;
            border-top: 3px solid var(--neon-yellow);
            box-shadow: 0 -5px 15px rgba(252, 238, 10, 0.2), inset 0 0 20px rgba(252, 238, 10, 0.05);
        }

        h2 {
            font-size: 1.8rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            align-items: center;
        }

        .panel-hft h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .panel-trinity h2 { color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); }
        .panel-market h2 { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        .squad-list { list-style: none; }
        .squad-item {
            margin-bottom: 15px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .hft-item { border-color: var(--neon-pink); }
        .trinity-item { border-color: var(--neon-cyan); }

        .squad-name {
            font-size: 1.2rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .squad-status {
            font-size: 0.9rem;
            padding: 3px 8px;
            background: rgba(57, 255, 20, 0.15);
            color: var(--neon-green);
            border: 1px solid var(--neon-green);
            border-radius: 2px;
            text-shadow: 0 0 5px var(--neon-green);
        }

        .status-warn {
            color: var(--neon-yellow);
            border-color: var(--neon-yellow);
            background: rgba(252, 238, 10, 0.15);
            text-shadow: 0 0 5px var(--neon-yellow);
        }

        .status-danger {
            color: var(--neon-red);
            border-color: var(--neon-red);
            background: rgba(255, 0, 60, 0.15);
            text-shadow: 0 0 5px var(--neon-red);
            animation: blink 1s infinite;
        }

        @keyframes blink { 50% { opacity: 0.5; } }

        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(0, 0, 0, 0.6);
        }

        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        th {
            color: var(--neon-yellow);
            text-transform: uppercase;
            letter-spacing: 2px;
            font-size: 1.1rem;
        }

        tr:hover {
            background: rgba(252, 238, 10, 0.05);
        }

        .signal-long { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        .signal-short { color: var(--neon-red); font-weight: bold; text-shadow: 0 0 5px var(--neon-red); }
        .signal-wait { color: var(--neon-yellow); font-weight: bold; text-shadow: 0 0 5px var(--neon-yellow); }

        .progress-bar {
            width: 100px;
            height: 10px;
            background: #222;
            border: 1px solid #444;
            display: inline-block;
            vertical-align: middle;
            margin-right: 10px;
        }

        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 5px var(--neon-green);
        }

        .console-output {
            margin-top: 20px;
            padding: 15px;
            background: #000;
            border: 1px solid #333;
            color: #aaa;
            font-size: 0.9rem;
            height: 120px;
            overflow-y: hidden;
            position: relative;
        }

        .console-line {
            margin-bottom: 5px;
            opacity: 0.8;
        }
        
        .console-line::before {
            content: "> ";
            color: var(--neon-cyan);
        }

        .sys-time {
            position: absolute;
            top: 20px;
            right: 40px;
            font-size: 1.2rem;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
        }

    </style>
</head>
<body>

    <header>
        <div class="sys-time" id="clock">00:00:00 UTC</div>
        <h1><span style="color:#fff;">[</span> ORBITAL COMMAND <span style="color:#fff;">]</span></h1>
        <div class="status-badge">SYSTEM SECURED // LATENCY: 3ms // UPTIME: 99.99%</div>
        <br>
        <div class="status-badge" style="margin-top: 10px; border-color: var(--neon-cyan); color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </header>

    <div class="dashboard-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul class="squad-list">
                <li class="squad-item hft-item">
                    <span class="squad-name">🐺 SQUADRA_ALPHA <span style="font-size:0.8rem; color:#888;">[Scalper Binance]</span></span>
                    <span class="squad-status">ENGAGED</span>
                </li>
                <li class="squad-item hft-item">
                    <span class="squad-name">🦅 SQUADRA_DELTA <span style="font-size:0.8rem; color:#888;">[Order Flow]</span></span>
                    <span class="squad-status">MONITORING</span>
                </li>
                <li class="squad-item hft-item">
                    <span class="squad-name">🐍 SQUADRA_GAMMA <span style="font-size:0.8rem; color:#888;">[Pairs Bitget]</span></span>
                    <span class="squad-status status-warn">REBALANCING</span>
                </li>
            </ul>
            <div class="console-output">
                <div class="console-line">ALPHA: Executed 43 trades in last 60s.</div>
                <div class="console-line">DELTA: Imbalance detected on ETH orderbook.</div>
                <div class="console-line">GAMMA: Z-Score spread expanding above 2.5 std dev.</div>
                <div class="console-line" style="color:var(--neon-green)">ALL TACTICAL UNITS RESPONDING.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul class="squad-list">
                <li class="squad-item trinity-item">
                    <span class="squad-name">🕴️ Lo Strozzino <span style="font-size:0.8rem; color:#888;">[Funding Arb]</span></span>
                    <span class="squad-status">COLLECTING YIELD</span>
                </li>
                <li class="squad-item trinity-item">
                    <span class="squad-name">🧮 Il Contabile <span style="font-size:0.8rem; color:#888;">[DCA Accumulation]</span></span>
                    <span class="squad-status">ONLINE</span>
                </li>
                <li class="squad-item trinity-item">
                    <span class="squad-name">👼 L'Angelo Custode <span style="font-size:0.8rem; color:#888;">[MEV Arbitrum]</span></span>
                    <span class="squad-status status-danger">SNIPING MEMPOOL</span>
                </li>
            </ul>
            <div class="console-output">
                <div class="console-line">Strozzino: Funding rate delta 0.045% (LONG ARB).</div>
                <div class="console-line">Contabile: BTC DCA trigger next in 4h 12m.</div>
                <div class="console-line">Angelo: Block 1984203 analyzed. Frontrun executed.</div>
                <div class="console-line" style="color:var(--neon-cyan)">BACKGROUND DAEMONS NOMINAL.</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-market">
            <h2>👁️ THE ORACLE // MARKET METRICS</h2>
            <table>
                <thead>
                    <tr>
                        <th>Modulo Sensore</th>
                        <th>Target Asset</th>
                        <th>Segnale Tattico</th>
                        <th>Confidence</th>
                        <th>Azione</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>🔮 The Oracle (Sentiment)</td>
                        <td>BTC/USDT</td>
                        <td class="signal-long">LONG (BULLISH)</td>
                        <td>
                            <div class="progress-bar"><div class="progress-fill" style="width: 89%;"></div></div> 89%
                        </td>
                        <td>[ HOLD ]</td>
                    </tr>
                    <tr>
                        <td>🐋 Whale Tracker</td>
                        <td>ETH/USDT</td>
                        <td class="signal-short">SHORT (DISTRIBUTION)</td>
                        <td>
                            <div class="progress-bar"><div class="progress-fill" style="width: 74%; background: var(--neon-red); box-shadow: 0 0 5px var(--neon-red);"></div></div> 74%
                        </td>
                        <td>[ HEDGE ]</td>
                    </tr>
                    <tr>
                        <td>🔮 The Oracle (Sentiment)</td>
                        <td>SOL/USDT</td>
                        <td class="signal-long">LONG (ACCUMULATION)</td>
                        <td>
                            <div class="progress-bar"><div class="progress-fill" style="width: 92%;"></div></div> 92%
                        </td>
                        <td>[ DEPLOY ALPHA ]</td>
                    </tr>
                    <tr>
                        <td>⚡ Dark Pool Monitor</td>
                        <td>BNB/USDT</td>
                        <td class="signal-wait">NEUTRAL (WAIT)</td>
                        <td>
                            <div class="progress-bar"><div class="progress-fill" style="width: 45%; background: var(--neon-yellow); box-shadow: 0 0 5px var(--neon-yellow);"></div></div> 45%
                        </td>
                        <td>[ STANDBY ]</td>
                    </tr>
                </tbody>
            </table>
        </div>

    </div>

    <script>
        // Clock
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }, 1000);

        // Simple Matrix rain effect for the console backgrounds? Nah, keep it clean.
        // Randomly update numbers to look alive
        setInterval(() => {
            const lines = document.querySelectorAll('.console-line');
            const target = lines[Math.floor(Math.random() * 3)]; // Randomly pick one of the first 3 lines of either console
            if(target && target.innerText.includes('Executed')) {
                const trades = Math.floor(Math.random() * 100);
                target.innerText = `ALPHA: Executed ${trades} trades in last 60s.`;
            }
        }, 2500);
    </script>
</body>
</html>"""

@app.route('/')
def dashboard():
    return HTML_CONTENT

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
