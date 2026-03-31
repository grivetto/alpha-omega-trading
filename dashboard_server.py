import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command - Cyberpunk Terminal</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-yellow: #faff00;
            --neon-red: #ff003c;
            --bg-base: #020202;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --grid-color: rgba(57, 255, 20, 0.05);
        }

        body {
            background-color: var(--bg-base);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            text-shadow: 0 0 5px rgba(57, 255, 20, 0.7);
        }

        /* CRT effects */
        body::after {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
            animation: scroll 10s linear infinite;
        }

        @keyframes scroll {
            0% { background-position: 0 0; }
            100% { background-position: 0 100vh; }
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
            position: relative;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 5px;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            animation: flicker 4s infinite alternate;
        }

        .status-dot {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red), 0 0 20px var(--neon-red);
            margin-right: 15px;
            animation: blink 1s infinite;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            z-index: 10;
            position: relative;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 20px;
            border-radius: 2px;
            position: relative;
            overflow: hidden;
        }

        /* Glitchy borders for panels */
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }

        .panel.blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.2);
        }
        .panel.blue::before, .panel.blue::after { border-color: var(--neon-blue); }
        .panel.blue h2 { text-shadow: 0 0 10px var(--neon-blue); }

        .panel.pink {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.1), 0 0 10px rgba(255, 0, 255, 0.2);
        }
        .panel.pink::before, .panel.pink::after { border-color: var(--neon-pink); }
        .panel.pink h2 { text-shadow: 0 0 10px var(--neon-pink); }

        .item {
            margin: 15px 0;
            padding: 10px;
            border-left: 3px solid;
            background: rgba(255, 255, 255, 0.03);
            transition: all 0.2s;
        }
        .item:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(5px);
        }

        .item-green { border-left-color: var(--neon-green); }
        .item-blue { border-left-color: var(--neon-blue); }
        .item-pink { border-left-color: var(--neon-pink); }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            font-size: 0.8em;
            background: var(--neon-green);
            color: #000;
            font-weight: bold;
            border-radius: 2px;
            margin-left: 10px;
            float: right;
            text-shadow: none;
        }
        .badge.blue { background: var(--neon-blue); }
        .badge.pink { background: var(--neon-pink); }
        .badge.yellow { background: var(--neon-yellow); }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9em; }
        th, td { border: 1px solid rgba(255, 0, 255, 0.3); padding: 10px; text-align: left; }
        th { color: var(--neon-pink); background: rgba(255, 0, 255, 0.1); }
        tr:hover { background: rgba(255, 0, 255, 0.05); }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: var(--neon-green);
            width: 78%;
            position: absolute;
            box-shadow: 0 0 5px var(--neon-green);
        }
        .progress-fill.blue { background: var(--neon-blue); width: 45%; box-shadow: 0 0 5px var(--neon-blue); }
        .progress-fill.pink { background: var(--neon-pink); width: 92%; box-shadow: 0 0 5px var(--neon-pink); }

        .blink-text { animation: blink 1.5s infinite; }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.2; }
        }

        @keyframes flicker {
            0%, 18%, 22%, 25%, 53%, 57%, 100% { text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.8; }
        }

        .terminal-log {
            font-size: 0.8em;
            opacity: 0.8;
            margin-top: 15px;
            height: 60px;
            overflow: hidden;
            border-top: 1px dashed rgba(255,255,255,0.2);
            padding-top: 10px;
        }

        .glitch-effect {
            position: relative;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="header">
        <h1><span class="status-dot"></span> ORBITAL COMMAND</h1>
        <p style="color: var(--neon-yellow); letter-spacing: 3px;">SYS.OP: NUVOLA NODE // QUANTITATIVE TACTICAL DASHBOARD</p>
        <p style="color: var(--neon-blue); font-weight: bold; letter-spacing: 2px; text-shadow: 0 0 5px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
        <p class="blink-text" style="font-size: 0.8em; margin-top: 10px;">[ ENCRYPTED UPLINK ESTABLISHED ]</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div style="font-size: 0.8em; color: var(--neon-yellow); margin-bottom: 10px;">TACTICAL UNITS DEPLOYED. HIGH-FREQUENCY MODE ENGAGED.</div>
            
            <div class="item item-green">
                <strong>[ SQUADRA_ALPHA ]</strong> ⚡ Binance Scalper
                <span class="badge">ENGAGED</span>
                <br><small>Ping: 8ms | Vol: $1.2M | PNL: <span style="color:var(--neon-green);">+1.24%</span></small>
                <div class="progress-bar"><div class="progress-fill"></div></div>
            </div>
            
            <div class="item item-green">
                <strong>[ SQUADRA_DELTA ]</strong> 🌊 Order Flow
                <span class="badge yellow" style="background:var(--neon-yellow);">HUNTING</span>
                <br><small>Target: Liquidity Voids | Heatmap: ACTIVE</small>
                <div class="progress-bar"><div class="progress-fill" style="width: 30%;"></div></div>
            </div>
            
            <div class="item item-green">
                <strong>[ SQUADRA_GAMMA ]</strong> ⚖️ Bitget Pairs
                <span class="badge">REBALANCING</span>
                <br><small>Strategy: Stat Arb | Exposure: Delta-Neutral</small>
                <div class="progress-bar"><div class="progress-fill" style="width: 60%;"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div style="background-color: rgba(0, 243, 255, 0.1); border: 1px solid var(--neon-blue); padding: 8px; font-weight: bold; text-align: center; margin-bottom: 15px; letter-spacing: 1px;">
                ⚙️ BACKGROUND SERVICES ONLINE ⚙️
            </div>
            
            <div class="item item-blue">
                <strong>🕴️ Lo Strozzino</strong> (Funding Arb)
                <span class="badge blue">YIELDING</span>
                <br><small>Spread: 0.045% | Position: Hedged | APY: 18.2%</small>
            </div>
            
            <div class="item item-blue">
                <strong>🧮 Il Contabile</strong> (DCA Core)
                <span class="badge blue">WAITING</span>
                <br><small>Next Accumulation: 14h 22m | Allocation: 100%</small>
            </div>
            
            <div class="item item-blue">
                <strong>🛡️ L'Angelo Custode</strong> (MEV Arbitrum)
                <span class="badge blue">SCANNING</span>
                <br><small>Mempool: Deep Scan | Gas: 0.12 gwei | TXs: 142/s</small>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div style="font-size: 0.8em; color: var(--neon-pink); margin-bottom: 10px;">GLOBAL INTELLIGENCE NETWORK</div>
            
            <table>
                <tr>
                    <th>MODULE</th>
                    <th>SOURCE</th>
                    <th>SIGNAL</th>
                </tr>
                <tr>
                    <td>The Oracle 🧿</td>
                    <td>Binance Sentiment</td>
                    <td style="color: var(--neon-green); font-weight:bold;">BULLISH 🟢</td>
                </tr>
                <tr>
                    <td>Whale Tracker 🐋</td>
                    <td>On-Chain Scraper</td>
                    <td style="color: var(--neon-yellow); font-weight:bold;">ACCUMULATING 🟡</td>
                </tr>
                <tr>
                    <td>Dark Pool Vol 📈</td>
                    <td>CEX APIs</td>
                    <td style="color: var(--neon-red); font-weight:bold;">ELEVATED 🔴</td>
                </tr>
            </table>
            
            <div class="terminal-log">
                > [SYS] Fetching Oracle data... OK.<br>
                > [SYS] Analyzing Whale wallets... 3 anomalies detected.<br>
                > [WARN] Volatility spike predicted in 2h window.<br>
                <span class="blink-text">> _</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
