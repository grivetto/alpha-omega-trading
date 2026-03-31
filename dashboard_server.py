from flask import Flask, render_template_string
import threading
import time
import random
import logging

# Disable default Flask logging to keep terminal clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA HQ</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-dark: #020204;
            --grid-line: #0a0a1a;
            --neon-blue: #00e5ff;
            --neon-pink: #ff0055;
            --neon-green: #00ff66;
            --neon-yellow: #ffcc00;
            --neon-purple: #b000ff;
            --neon-red: #ff1100;
            --text-main: #c0f8ff;
            --panel-bg: rgba(4, 4, 12, 0.85);
            --border-glow: 0 0 10px rgba(0, 229, 255, 0.5);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            background-position: center center;
            overflow-x: hidden;
        }

        /* Scanline effect */
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

        h1, h2, h3, h4 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 0 0 10px 0;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 25px rgba(0, 229, 255, 0.15);
            position: relative;
            background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.1), transparent);
        }
        
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            font-size: 3em;
            letter-spacing: 5px;
        }
        
        .header p {
            color: var(--neon-pink);
            font-size: 1.2em;
            letter-spacing: 3px;
            text-shadow: 0 0 5px var(--neon-pink);
        }

        .blink {
            animation: blinker 1.2s cubic-bezier(0.5, 0, 1, 1) infinite alternate;
        }
        
        @keyframes blinker {  
            0% { opacity: 1; }
            100% { opacity: 0; }
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid;
            border-radius: 4px;
            padding: 25px;
            position: relative;
            backdrop-filter: blur(4px);
            transition: all 0.3s ease;
        }
        
        /* Corner decorations */
        .panel::before, .panel::after {
            content: ''; position: absolute; width: 20px; height: 20px;
            pointer-events: none;
        }
        .panel::before { top: -1px; left: -1px; border-top: 2px solid; border-left: 2px solid; }
        .panel::after { bottom: -1px; right: -1px; border-bottom: 2px solid; border-right: 2px solid; }
        
        /* Specific panel colors */
        .panel.hft { 
            border-color: var(--neon-blue); 
            box-shadow: inset 0 0 20px rgba(0, 229, 255, 0.05), 0 0 15px rgba(0, 229, 255, 0.2);
        }
        .panel.hft::before, .panel.hft::after { border-color: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        .panel.hft h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        .panel.trinity { 
            border-color: var(--neon-purple); 
            box-shadow: inset 0 0 20px rgba(176, 0, 255, 0.05), 0 0 15px rgba(176, 0, 255, 0.2);
            background: rgba(15, 4, 20, 0.85);
        }
        .panel.trinity::before, .panel.trinity::after { border-color: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        .panel.trinity h2 { color: var(--neon-purple); text-shadow: 0 0 8px var(--neon-purple); }

        .panel.metrics { 
            border-color: var(--neon-green); 
            box-shadow: inset 0 0 20px rgba(0, 255, 102, 0.05), 0 0 15px rgba(0, 255, 102, 0.2);
        }
        .panel.metrics::before, .panel.metrics::after { border-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        .panel.metrics h2 { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }

        .section-title {
            border-bottom: 1px dashed rgba(255, 255, 255, 0.2);
            padding-bottom: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .card {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid;
        }

        .card.alpha { border-left-color: var(--neon-blue); }
        .card.delta { border-left-color: var(--neon-pink); }
        .card.gamma { border-left-color: var(--neon-yellow); }
        .card.strozzino { border-left-color: var(--neon-red); }
        .card.contabile { border-left-color: var(--neon-green); }
        .card.angelo { border-left-color: var(--neon-blue); }
        .card.oracle { border-left-color: var(--neon-purple); }
        .card.whale { border-left-color: var(--neon-blue); }

        .card h3 {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 1.1em;
            color: #fff;
        }

        .status-badge {
            font-size: 0.7em;
            padding: 3px 8px;
            border-radius: 2px;
            background: rgba(0, 255, 102, 0.1);
            color: var(--neon-green);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 5px rgba(0, 255, 102, 0.5);
        }
        
        .status-badge.warning {
            background: rgba(255, 204, 0, 0.1);
            color: var(--neon-yellow);
            border-color: var(--neon-yellow);
            box-shadow: 0 0 5px rgba(255, 204, 0, 0.5);
        }

        .status-badge.active {
            background: rgba(0, 229, 255, 0.1);
            color: var(--neon-blue);
            border-color: var(--neon-blue);
            box-shadow: 0 0 5px rgba(0, 229, 255, 0.5);
            animation: pulse-blue 2s infinite;
        }

        @keyframes pulse-blue {
            0% { box-shadow: 0 0 5px rgba(0, 229, 255, 0.5); }
            50% { box-shadow: 0 0 15px rgba(0, 229, 255, 0.8); }
            100% { box-shadow: 0 0 5px rgba(0, 229, 255, 0.5); }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .data-item {
            display: flex;
            flex-direction: column;
            background: rgba(255,255,255,0.03);
            padding: 8px;
            border-radius: 2px;
        }

        .data-label { color: #6a8b99; font-size: 0.8em; text-transform: uppercase; }
        .data-value { font-size: 1.2em; font-weight: bold; margin-top: 5px; color: #fff; text-shadow: 0 0 4px rgba(255,255,255,0.3); }
        
        .val-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .val-down { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .val-neutral { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .val-alert { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); animation: blinker 1s infinite; }

        .terminal {
            background: rgba(0, 0, 0, 0.8);
            padding: 15px;
            border: 1px solid #333;
            border-top: 1px solid var(--neon-green);
            height: 200px;
            overflow-y: hidden;
            font-size: 0.9em;
            color: var(--neon-green);
            margin-top: 20px;
            position: relative;
        }

        .terminal::before {
            content: 'TERMINAL OUT // SYS_LOG';
            position: absolute;
            top: 0; right: 0;
            background: var(--neon-green);
            color: #000;
            font-size: 0.7em;
            padding: 2px 10px;
            font-weight: bold;
        }

        .terminal-lines {
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }

        .t-line { margin: 2px 0; opacity: 0.8; }
        .t-line.new { animation: fade-in 0.3s forwards; }
        
        @keyframes fade-in {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        /* Matrix rain decorative elements */
        .decor-bar {
            height: 4px;
            width: 100%;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            margin: 20px 0;
            opacity: 0.5;
        }
        
        .protocol-banner {
            text-align: center;
            padding: 10px;
            background: repeating-linear-gradient(45deg, rgba(176,0,255,0.1), rgba(176,0,255,0.1) 10px, rgba(0,0,0,0) 10px, rgba(0,0,0,0) 20px);
            border: 1px solid var(--neon-purple);
            color: var(--neon-purple);
            font-weight: bold;
            letter-spacing: 3px;
            margin-bottom: 20px;
            text-shadow: 0 0 5px var(--neon-purple);
        }

    </style>
</head>
<body>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND <span class="blink">_</span></h1>
        <p>/// NUVOLA TACTICAL DASHBOARD /// SECURE UPLINK ESTABLISHED ///</p>
        <div style="margin-top: 15px; font-size: 1.5em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); font-weight: bold; padding: 10px; border: 1px solid var(--neon-green); display: inline-block; background: rgba(0, 255, 102, 0.1); border-radius: 4px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel hft">
            <h2 class="section-title">⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            
            <div class="card alpha">
                <h3>SQUADRA_ALPHA <span class="status-badge active">ENGAGING</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Target / Role</span>
                        <span class="data-value">Binance Scalper ⚡</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">APM (Actions/Min)</span>
                        <span class="data-value val-neutral" id="alpha-apm">1,402</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Win Rate (24H)</span>
                        <span class="data-value val-up">68.4% ▲</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Latency</span>
                        <span class="data-value">12ms</span>
                    </div>
                </div>
            </div>
            
            <div class="card delta">
                <h3>SQUADRA_DELTA <span class="status-badge">MONITORING</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Target / Role</span>
                        <span class="data-value">Order Flow 🌊</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Depth Scanned</span>
                        <span class="data-value">L3 Orderbook</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Imbalance</span>
                        <span class="data-value val-down" id="delta-imb">+4.2% ASK</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Signal</span>
                        <span class="data-value val-alert">SELL PRESSURE</span>
                    </div>
                </div>
            </div>
            
            <div class="card gamma">
                <h3>SQUADRA_GAMMA <span class="status-badge active">HEDGED</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Target / Role</span>
                        <span class="data-value">Bitget Pairs ⚖️</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Active Pair</span>
                        <span class="data-value">BTC-ETH / SOL-AVAX</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Z-Score</span>
                        <span class="data-value val-neutral" id="gamma-z">2.14 σ</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Spread</span>
                        <span class="data-value val-up">0.12%</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 class="section-title">🛡️ PROTOCOLLO TRINITY</h2>
            
            <div class="protocol-banner">
                SYSTEMS ONLINE // BACKGROUND OPERATION ACTIVE
            </div>
            
            <div class="card strozzino">
                <h3>LO STROZZINO 💰 <span class="status-badge">EXTRACTING</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Operation</span>
                        <span class="data-value">Funding Arb</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Target Exchange</span>
                        <span class="data-value">Bybit / OKX</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Current Yield</span>
                        <span class="data-value val-up" id="stroz-yield">14.2% APY</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Capital Deployed</span>
                        <span class="data-value">$45,000.00</span>
                    </div>
                </div>
            </div>
            
            <div class="card contabile">
                <h3>IL CONTABILE 📊 <span class="status-badge warning">STANDBY</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Operation</span>
                        <span class="data-value">DCA Accumulator</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Asset Focus</span>
                        <span class="data-value">BTC / ETH / TIA</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Next Execution</span>
                        <span class="data-value val-neutral" id="contabile-timer">04:12:00</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Avg Entry (BTC)</span>
                        <span class="data-value">$61,240</span>
                    </div>
                </div>
            </div>
            
            <div class="card angelo">
                <h3>L'ANGELO CUSTODE 🛡️ <span class="status-badge active">GUARDING</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Operation</span>
                        <span class="data-value">MEV Protection</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Network</span>
                        <span class="data-value">Arbitrum One</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Sandwich Tx Blocked</span>
                        <span class="data-value val-up" id="angelo-blocked">1,432</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Slippage Saved</span>
                        <span class="data-value val-green">~$1,204</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2 class="section-title">📡 METRICHE DI MERCATO</h2>
            
            <div class="card oracle">
                <h3>THE ORACLE 🔮 <span class="status-badge active">SYNCED</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Data Source</span>
                        <span class="data-value">Binance Sentiment + X</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Fear & Greed</span>
                        <span class="data-value val-up" id="oracle-fg">GREED (72)</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Retail Liquidations</span>
                        <span class="data-value val-down">$45.2M (Shorts)</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Volatility Index</span>
                        <span class="data-value val-alert">ELEVATED</span>
                    </div>
                </div>
            </div>
            
            <div class="card whale">
                <h3>WHALE TRACKER 🐋 <span class="status-badge">PINGING</span></h3>
                <div class="data-grid">
                    <div class="data-item">
                        <span class="data-label">Netflow 24H</span>
                        <span class="data-value val-down">-1,200 BTC</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Exchange Reserves</span>
                        <span class="data-value val-down">Draining ▼</span>
                    </div>
                    <div class="data-item" style="grid-column: span 2;">
                        <span class="data-label">Last Major Tx Trace</span>
                        <span class="data-value" style="font-size: 1em; color: var(--neon-blue);" id="whale-tx">500 BTC -> Coinbase Prime (OTC)</span>
                    </div>
                </div>
            </div>

            <div class="decor-bar"></div>

            <div class="terminal">
                <div class="terminal-lines" id="sys-log">
                    <div class="t-line">> SYSTEM BOOT SEQUENCE... OK</div>
                    <div class="t-line">> ESTABLISHING SECURE SOCKETS... OK</div>
                    <div class="t-line">> SQUADRA_ALPHA: Connected to Binance WebSocket.</div>
                    <div class="t-line">> PROTOCOLLO TRINITY: Background daemon running. PID 4092.</div>
                    <div class="t-line">> AWAITING INSTRUCTIONS...</div>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Simulate real-time updates for that quantitative dashboard feel
        
        // Timer for Il Contabile
        let secondsLeft = 4 * 3600 + 12 * 60;
        setInterval(() => {
            secondsLeft--;
            const h = Math.floor(secondsLeft / 3600).toString().padStart(2, '0');
            const m = Math.floor((secondsLeft % 3600) / 60).toString().padStart(2, '0');
            const s = (secondsLeft % 60).toString().padStart(2, '0');
            document.getElementById('contabile-timer').innerText = `${h}:${m}:${s}`;
        }, 1000);

        // Terminal Logs
        const terminal = document.getElementById('sys-log');
        const logs = [
            "> [ALPHA] Scalp execution filled @ limit. PnL +$12.40",
            "> [ALPHA] Canceling resting bids, volatility spike detected.",
            "> [DELTA] Ask wall spotted at $65,000. 450 BTC.",
            "> [DELTA] Order book imbalance neutralized. Spread normalized.",
            "> [GAMMA] Rebalancing SOL-AVAX hedge ratio.",
            "> [STROZZINO] Funding rate adjusted on Bybit. Recalculating APY.",
            "> [ANGELO] Sandwich bot detected. Transaction routed through Flashbots.",
            "> [ORACLE] Sentiment index shifted +2 points. Greed increasing.",
            "> [WHALE] Alert: 10,000 ETH moved from Binance to Unknown Wallet.",
            "> [SYS] Latency check: Binance 11ms, Bitget 18ms, Arbitrum RPC 45ms."
        ];
        
        setInterval(() => {
            if (Math.random() > 0.4) {
                // Remove oldest if too many
                if (terminal.children.length > 8) {
                    terminal.removeChild(terminal.firstChild);
                }
                
                const logLine = document.createElement('div');
                logLine.className = 't-line new';
                
                const now = new Date();
                const timeStr = now.getHours().toString().padStart(2, '0') + ':' + 
                              now.getMinutes().toString().padStart(2, '0') + ':' + 
                              now.getSeconds().toString().padStart(2, '0');
                
                logLine.innerHTML = `<span style="color:#555">[${timeStr}]</span> ${logs[Math.floor(Math.random() * logs.length)]}`;
                terminal.appendChild(logLine);
            }
        }, 2500);

        // Randomly update numbers
        setInterval(() => {
            // APM
            const apm = parseInt(document.getElementById('alpha-apm').innerText.replace(',', ''));
            const newApm = apm + Math.floor(Math.random() * 50) - 25;
            document.getElementById('alpha-apm').innerText = newApm.toLocaleString();
            
            // Gamma Z-score
            const z = (2.0 + Math.random() * 0.4).toFixed(2);
            document.getElementById('gamma-z').innerText = z + ' σ';
            
            // Blocked txs
            if (Math.random() > 0.8) {
                const blocked = parseInt(document.getElementById('angelo-blocked').innerText.replace(',', ''));
                document.getElementById('angelo-blocked').innerText = (blocked + 1).toLocaleString();
            }
            
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Starting Orbital Command Dashboard on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)
