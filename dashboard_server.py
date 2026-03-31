import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-red: #ff003c;
            --dark-bg: #050505;
            --panel-bg: #0a0f0a;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px var(--neon-green);
            text-transform: uppercase;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px var(--neon-cyan);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 10px rgba(57, 255, 20, 0.2);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status-online { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .status-active { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 2s infinite; }
        .status-warning { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #1f3f1f; padding: 8px; text-align: left; }
        th { background-color: #112211; color: var(--neon-cyan); }
        
        .hud-line { display: flex; justify-content: space-between; border-bottom: 1px dashed #1f3f1f; margin: 5px 0; padding: 2px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND - NUVOLA NODE 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online">FULLY OPERATIONAL</span> | UPTIME: 99.99% | SECURE CONNECTION</p>
        <p style="font-size: 1.2em; font-weight: bold; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: <span class="status-active">Online (DCA, Funding, MEV)</span></p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="hud-line">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status-active">[ ENGAGED ]</span>
            </div>
            <div class="hud-line">
                <span>🎯 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-active">[ MONITORING ]</span>
            </div>
            <div class="hud-line">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status-active">[ ARBITRAGE ]</span>
            </div>
            <p style="font-size: 0.8em; margin-top:15px; color:#aaa;">&gt; Executing sub-millisecond strikes on liquidity pockets...</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="hud-line">
                <span>🏦 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ BACKGROUND ]</span>
            </div>
            <div class="hud-line">
                <span>🧮 Il Contabile (DCA Matrix)</span>
                <span class="status-online">[ ACTIVE ]</span>
            </div>
            <div class="hud-line">
                <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">[ SHIELDED ]</span>
            </div>
            <p style="font-size: 0.8em; margin-top:15px; color:#aaa;">&gt; Core wealth preservation protocols running silently.</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO (THE ORACLE)</h2>
            <table>
                <tr>
                    <th>METRIC</th>
                    <th>VALUE</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td>Binance Sentiment</td>
                    <td>68.4 (GREED)</td>
                    <td class="status-active">LONG BIAS</td>
                </tr>
                <tr>
                    <td>Whale Tracker</td>
                    <td>+4500 BTC</td>
                    <td class="status-online">ACCUMULATION</td>
                </tr>
                <tr>
                    <td>Orderbook Imbalance</td>
                    <td>-12.5%</td>
                    <td class="status-warning">DEFENSIVE</td>
                </tr>
            </table>
        </div>
        
        <!-- TERMINAL FEED -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>💻 LIVE TERMINAL FEED</h2>
            <div id="terminal" style="font-size: 0.9em; height: 100px; overflow-y: hidden; color: var(--neon-cyan);">
                &gt; Initializing quant models... OK<br>
                &gt; Connecting to Binance API... OK<br>
                &gt; Loading Arbitrum mempool scanners... OK<br>
                &gt; ALL SYSTEMS NOMINAL. AWAITING ORDERS.
            </div>
        </div>
    </div>
    <script>
        const terminal = document.getElementById('terminal');
        const logs = [
            "&gt; Alpha squad identified micro-inefficiency in BTC/USDT...",
            "&gt; Executing flash-fill... Success.",
            "&gt; The Oracle detects anomalous volume on ETH derivatives.",
            "&gt; Shielding capital against downside volatility spike.",
            "&gt; Recalculating funding rates... Arb opportunity: 0.045%."
        ];
        setInterval(() => {
            const newLog = logs[Math.floor(Math.random() * logs.length)];
            terminal.innerHTML += '<br>' + newLog;
            if (terminal.innerHTML.split('<br>').length > 6) {
                terminal.innerHTML = terminal.innerHTML.substring(terminal.innerHTML.indexOf('<br>') + 4);
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
