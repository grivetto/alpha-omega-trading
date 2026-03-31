import os
import time
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --bg-color: #030308;
            --neon-green: #00ff00;
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --neon-red: #ff003c;
            --neon-yellow: #fcee0a;
            --panel-bg: rgba(0, 20, 0, 0.4);
            --font-main: 'Courier New', Courier, monospace;
        }

        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }

        body, html {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', var(--font-main);
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow-x: hidden;
            text-transform: uppercase;
        }

        /* CRT effects */
        body::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        body::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: radial-gradient(circle, rgba(0,0,0,0) 60%, rgba(0,0,0,0.6) 100%);
            z-index: 1000;
            pointer-events: none;
        }

        .scanline {
            width: 100%;
            height: 5px;
            z-index: 9998;
            position: fixed;
            pointer-events: none;
            background: rgba(0, 255, 0, 0.3);
            opacity: 0.4;
            animation: scanline 8s linear infinite;
            box-shadow: 0 0 10px rgba(0,255,0,0.5);
        }

        @keyframes scanline {
            0% { top: -5%; }
            100% { top: 105%; }
        }

        header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.2);
            position: relative;
            background: rgba(0, 20, 20, 0.8);
            z-index: 10;
        }

        h1 {
            font-size: 3em;
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue);
            margin: 0;
            letter-spacing: 10px;
            animation: textGlitch 2s infinite alternate;
        }

        .sys-clock {
            position: absolute;
            top: 25px;
            right: 30px;
            font-size: 1.5em;
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow);
            border: 1px solid var(--neon-yellow);
            padding: 5px 15px;
            background: rgba(252, 238, 10, 0.1);
        }

        .wrapper {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            padding: 30px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 0, 0.1), 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 15px; height: 15px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 15px; height: 15px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }

        .panel h2 {
            margin-top: 0;
            font-size: 1.6em;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
            text-shadow: 0 0 5px var(--neon-green);
        }

        /* Specific Panel Colors */
        .panel.trinity {
            border-color: var(--neon-pink);
            box-shadow: inset 0 0 15px rgba(255, 0, 255, 0.1), 0 0 10px rgba(255, 0, 255, 0.2);
        }
        .panel.trinity::before, .panel.trinity::after { border-color: var(--neon-pink); }
        .panel.trinity h2 { border-bottom-color: var(--neon-pink); color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }

        .panel.market {
            border-color: var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1), 0 0 10px rgba(0, 255, 255, 0.2);
        }
        .panel.market::before, .panel.market::after { border-color: var(--neon-blue); }
        .panel.market h2 { border-bottom-color: var(--neon-blue); color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }

        .squad-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .squad-item {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 3px solid var(--neon-green);
            position: relative;
            overflow: hidden;
        }

        .trinity .squad-item { border-left-color: var(--neon-pink); }
        .market .squad-item { border-left-color: var(--neon-blue); }

        .squad-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        .squad-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 1.2em;
            font-weight: bold;
        }

        .status-badge {
            padding: 3px 10px;
            font-size: 0.75em;
            color: #000;
            font-weight: bold;
            box-shadow: 0 0 10px currentColor;
            letter-spacing: 1px;
        }

        .status-active { background: var(--neon-green); animation: pulse 1.5s infinite; }
        .status-standby { background: var(--neon-yellow); }
        .status-deploy { background: var(--neon-pink); animation: pulse-fast 0.5s infinite; }
        .status-scan { background: var(--neon-blue); }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .metric-box {
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 10px;
            text-align: center;
            background: rgba(0,0,0,0.6);
        }

        .metric-label {
            font-size: 0.8em;
            color: #aaa;
            margin-bottom: 5px;
        }

        .metric-value {
            font-size: 1.4em;
            font-weight: bold;
            text-shadow: 0 0 5px currentColor;
        }

        /* Animations */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        @keyframes pulse-fast {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }

        @keyframes textGlitch {
            0% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            50% { text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-blue); }
            100% { text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
        }

        .radar {
            width: 40px; height: 40px;
            border-radius: 50%;
            border: 1px solid var(--neon-blue);
            position: relative;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
        }
        .radar::after {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            width: 50%; height: 50%;
            background: linear-gradient(45deg, rgba(0,255,255,0) 0%, rgba(0,255,255,0.8) 100%);
            transform-origin: 0 0;
            animation: radarSpin 2s linear infinite;
        }
        @keyframes radarSpin {
            100% { transform: rotate(360deg); }
        }

        /* Ticker */
        .ticker-wrap {
            width: 100%;
            background: var(--neon-red);
            color: #000;
            padding: 5px 0;
            position: fixed;
            bottom: 0;
            z-index: 100;
            font-weight: bold;
            overflow: hidden;
            white-space: nowrap;
        }
        .ticker-move {
            display: inline-block;
            animation: ticker 20s linear infinite;
            padding-left: 100%;
        }
        @keyframes ticker {
            0% { transform: translate3d(0, 0, 0); }
            100% { transform: translate3d(-100%, 0, 0); }
        }
        
        /* Terminal Log */
        .terminal {
            grid-column: 1 / -1;
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid #333;
            height: 200px;
            padding: 15px;
            overflow-y: hidden;
            position: relative;
            font-size: 0.9em;
        }
        .terminal::before {
            content: "SYSTEM LOG // LIVE FEED";
            position: absolute;
            top: 0; left: 0; width: 100%;
            background: #333; color: #fff;
            padding: 2px 10px; font-size: 0.8em;
            box-sizing: border-box;
        }
        .log-container {
            margin-top: 20px;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .log-entry {
            color: #aaa;
            animation: fadeIn 0.3s ease-in;
        }
        .log-entry .timestamp { color: var(--neon-yellow); margin-right: 10px; }
        .log-entry .source { color: var(--neon-blue); margin-right: 10px; }
        .log-entry.alert { color: var(--neon-red); }
        .log-entry.success { color: var(--neon-green); }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <header>
        <h1>[ NUVOLA ORBITAL COMMAND ]</h1>
        <div style="margin-top: 10px; font-size: 1.2em; color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
        <div class="sys-clock" id="clock">00:00:00 UTC</div>
    </header>

    <div class="wrapper">
        <!-- HFT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-header">
                        <span>🚀 SQUADRA_ALPHA (Binance Scalp)</span>
                        <span class="status-badge status-active">ENGAGED - LONG</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Latency (ms)</div>
                            <div class="metric-value" style="color:var(--neon-green)">12.4</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Win Rate / PnL</div>
                            <div class="metric-value" style="color:var(--neon-green)">68.4% / +$420</div>
                        </div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-header">
                        <span>🎯 SQUADRA_DELTA (Order Flow)</span>
                        <span class="status-badge status-scan">SCANNING BOOK</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Spoof Walls Detected</div>
                            <div class="metric-value" style="color:var(--neon-yellow)">3</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">CVD Imbalance</div>
                            <div class="metric-value" style="color:var(--neon-red)">-1.5%</div>
                        </div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-header">
                        <span>⚖️ SQUADRA_GAMMA (Pairs Trade)</span>
                        <span class="status-badge status-standby">AWAITING SIGNAL</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Target Spread</div>
                            <div class="metric-value" style="color:var(--neon-yellow)">0.18%</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Current Z-Score</div>
                            <div class="metric-value" style="color:var(--neon-green)">1.85</div>
                        </div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>⚡ PROTOCOLLO TRINITY <span class="status-badge status-active" style="margin-left:auto;font-size:0.5em;">ONLINE BACKGROUND</span></h2>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-header">
                        <span>💰 Lo Strozzino (Funding Arb)</span>
                        <span class="status-badge status-active">YIELD FARMING</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Est. APR</div>
                            <div class="metric-value" style="color:var(--neon-pink)">22.5%</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Delta Exposure</div>
                            <div class="metric-value" style="color:var(--neon-pink)">NEUTRAL</div>
                        </div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-header">
                        <span>📈 Il Contabile (DCA Engine)</span>
                        <span class="status-badge status-active">ACCUMULATING</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Next Buy Execution</div>
                            <div class="metric-value" style="color:var(--neon-pink)">14h 22m</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Portfolio Avg Cost</div>
                            <div class="metric-value" style="color:var(--neon-pink)">$54,210</div>
                        </div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-header">
                        <span>🛡️ L'Angelo Custode (MEV Arb)</span>
                        <span class="status-badge status-deploy">PROWLING MEMPOOL</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Blocks Scanned</div>
                            <div class="metric-value" style="color:var(--neon-pink)" id="mev-blocks">1,024,192</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Profitable Snipes</div>
                            <div class="metric-value" style="color:var(--neon-pink)">3 (+$125)</div>
                        </div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel market">
            <h2>👁️ THE ORACLE & WHALE TRACKER</h2>
            <ul class="squad-list">
                <li class="squad-item">
                    <div class="squad-header">
                        <span>🔮 The Oracle (Sentiment NLP)</span>
                        <span class="status-badge status-scan">INGESTING DATA</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">Fear & Greed Index</div>
                            <div class="metric-value" style="color:var(--neon-blue)">75 <span style="font-size:0.5em">(GREED)</span></div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">AI Trend Bias</div>
                            <div class="metric-value" style="color:var(--neon-blue)">BULLISH</div>
                        </div>
                    </div>
                </li>
                <li class="squad-item">
                    <div class="squad-header">
                        <span>🐋 Whale Tracker <div class="radar"></div></span>
                        <span class="status-badge status-active">TRACKING TXS</span>
                    </div>
                    <div class="metrics-grid">
                        <div class="metric-box">
                            <div class="metric-label">24H Net Inflow (CEX)</div>
                            <div class="metric-value" style="color:var(--neon-blue)">+$142M</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Massive TX Alerts</div>
                            <div class="metric-value" style="color:var(--neon-red)">CRITICAL (1)</div>
                        </div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- TERMINAL LOG -->
        <div class="panel terminal">
            <div class="log-container" id="terminal-logs">
                <div class="log-entry"><span class="timestamp">[SYS]</span> <span class="source">[INIT]</span> NUVOLA ORBITAL COMMAND ONLINE.</div>
                <div class="log-entry"><span class="timestamp">[SYS]</span> <span class="source">[AUTH]</span> SECURE HANDSHAKE ACCEPTED.</div>
            </div>
        </div>
    </div>

    <!-- TICKER -->
    <div class="ticker-wrap">
        <div class="ticker-move">
            🚨 ALERT: WHALE WALLET 0x8a...9f MOVED 2000 BTC TO BINANCE 🚨 || 💰 STROZZINO YIELD UPDATE: BYBIT FUNDING AT 0.05% || ⚡ ALPHA SQUAD EXECUTED LIMIT BUY 0.5 BTC @ $68,400 || 🛡️ ANGELO CUSTODE SAVED $42 ON GAS || 📈 IL CONTABILE DCA COMPLETED FOR TODAY || 🔮 THE ORACLE: TWITTER SENTIMENT SHIFTING BEARISH ON ALTCOINS...
        </div>
    </div>

    <script>
        // Clock
        setInterval(() => {
            const d = new Date();
            document.getElementById('clock').innerText = d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        }, 1000);

        // Fake MEV Counter
        let blocks = 1024192;
        setInterval(() => {
            blocks += Math.floor(Math.random() * 5);
            document.getElementById('mev-blocks').innerText = blocks.toLocaleString();
        }, 1500);

        // Terminal Output Generator
        const logLines = [
            { src: 'ALPHA', msg: 'Adjusting trailing stop loss for BTC position (+1.2%).', type: 'success' },
            { src: 'DELTA', msg: 'Order flow imbalance detected on ETH/USDT: Sell pressure rising.', type: 'alert' },
            { src: 'GAMMA', msg: 'Spread widening on SOL/USDT. Z-Score approaching 2.0...', type: '' },
            { src: 'STROZZINO', msg: 'Rebalancing margin on OKX. Delta remains neutral.', type: 'success' },
            { src: 'ANGELO', msg: 'Mempool gas spike detected. Pausing arb snipes momentarily.', type: 'alert' },
            { src: 'ORACLE', msg: 'Ingested 4,500 new tweets. NLP confidence 89%.', type: '' },
            { src: 'WHALE', msg: '15,000 ETH transferred from Unknown to Coinbase.', type: 'alert' }
        ];

        const terminal = document.getElementById('terminal-logs');
        setInterval(() => {
            const timeStr = new Date().toISOString().substring(11, 19);
            const rLog = logLines[Math.floor(Math.random() * logLines.length)];
            
            const div = document.createElement('div');
            div.className = 'log-entry ' + rLog.type;
            div.innerHTML = `<span class="timestamp">[${timeStr}]</span> <span class="source">[${rLog.src}]</span> ${rLog.msg}`;
            
            terminal.appendChild(div);
            
            if (terminal.children.length > 8) {
                terminal.removeChild(terminal.firstChild);
            }
        }, 3200);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
