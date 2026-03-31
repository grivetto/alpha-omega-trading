from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA HQ</title>
    <style>
        :root {
            --bg-color: #050510;
            --grid-color: #1a1a3a;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff2a2a;
            --text-main: #e0e0ff;
            --panel-bg: rgba(10, 10, 25, 0.85);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 15px rgba(0, 243, 255, 0.2);
            position: relative;
        }
        
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin: 0;
            font-size: 2.5em;
        }
        
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        
        @keyframes blinker {
            50% { opacity: 0; }
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
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        
        .panel h2 {
            margin-top: 0;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            border-bottom: 1px dashed #444;
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
        }
        
        .status-offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 8px var(--neon-red);
        }

        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 5px;
            background: rgba(255, 255, 255, 0.03);
            border-left: 2px solid var(--neon-blue);
        }

        .data-label { color: #888; font-size: 0.9em; }
        .data-value { font-weight: bold; color: var(--neon-green); }
        .data-value.danger { color: var(--neon-red); }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 10vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(0,243,255,0.1), rgba(255,255,255,0));
            opacity: 0.1;
            animation: scanline 8s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        
        @keyframes scanline {
            0% { top: -10vh; }
            100% { top: 110vh; }
        }

        .terminal {
            background: #000;
            padding: 15px;
            border: 1px solid #333;
            height: 150px;
            overflow-y: auto;
            font-size: 0.85em;
            color: var(--neon-green);
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND <span class="blink">_</span></h1>
        <p>NUVOLA QUANTITATIVE TRADING HUB - CLASSIFIED</p>
    </div>

    <div class="container">
        <!-- HFT TEAMS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div style="margin-bottom: 15px;">
                <h3><span class="status-indicator"></span> SQUADRA_ALPHA</h3>
                <div class="data-row"><span class="data-label">Role:</span> <span>Binance Scalper ⚡</span></div>
                <div class="data-row"><span class="data-label">Status:</span> <span class="data-value">ENGAGING TARGETS</span></div>
                <div class="data-row"><span class="data-label">Win Rate:</span> <span class="data-value" id="alpha-wr">68.4%</span></div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <h3><span class="status-indicator"></span> SQUADRA_DELTA</h3>
                <div class="data-row"><span class="data-label">Role:</span> <span>Order Flow 🌊</span></div>
                <div class="data-row"><span class="data-label">Status:</span> <span class="data-value">MONITORING DEPTH</span></div>
                <div class="data-row"><span class="data-label">Imbalance detected:</span> <span class="data-value danger">+4.2% ASK</span></div>
            </div>
            
            <div>
                <h3><span class="status-indicator"></span> SQUADRA_GAMMA</h3>
                <div class="data-row"><span class="data-label">Role:</span> <span>Bitget Pairs Trading ⚖️</span></div>
                <div class="data-row"><span class="data-label">Status:</span> <span class="data-value">HEDGED</span></div>
                <div class="data-row"><span class="data-label">Spread:</span> <span class="data-value" style="color:var(--neon-blue)">0.12%</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-green)">
            <h2 style="color: var(--neon-green)">🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; background: rgba(57, 255, 20, 0.1); border: 1px solid var(--neon-green); text-align: center; font-weight: bold; color: var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            
            <div style="margin-bottom: 15px;">
                <h3><span class="status-indicator"></span> LO STROZZINO</h3>
                <div class="data-row"><span class="data-label">Strategy:</span> <span>Funding Arb 💰</span></div>
                <div class="data-row"><span class="data-label">Est. APY:</span> <span class="data-value">14.2%</span></div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <h3><span class="status-indicator"></span> IL CONTABILE</h3>
                <div class="data-row"><span class="data-label">Strategy:</span> <span>DCA Accumulator 📊</span></div>
                <div class="data-row"><span class="data-label">Next Buy:</span> <span class="data-value" style="color:var(--neon-blue)">in 4h 12m</span></div>
            </div>
            
            <div>
                <h3><span class="status-indicator"></span> L'ANGELO CUSTODE</h3>
                <div class="data-row"><span class="data-label">Strategy:</span> <span>Arbitrum MEV Protection 🛡️</span></div>
                <div class="data-row"><span class="data-label">Tx Blocked:</span> <span class="data-value">1,432</span></div>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel" style="border-color: var(--neon-pink)">
            <h2 style="color: var(--neon-blue)">📡 METRICHE DI MERCATO</h2>
            
            <div style="margin-bottom: 15px;">
                <h3>THE ORACLE</h3>
                <div class="data-row"><span class="data-label">Binance Sentiment:</span> <span class="data-value" style="color:var(--neon-pink)">GREED (72)</span></div>
                <div class="data-row"><span class="data-label">Volatility Index:</span> <span class="data-value danger">ELEVATED</span></div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <h3>WHALE TRACKER 🐋</h3>
                <div class="data-row"><span class="data-label">Last Major Tx:</span> <span>500 BTC -> Coinbase</span></div>
                <div class="data-row"><span class="data-label">Netflow 24h:</span> <span class="data-value danger">-1,200 BTC</span></div>
            </div>

            <div class="terminal" id="sys-log">
                > Initializing Orbital Command... [OK]<br>
                > Connecting to Binance API... [OK]<br>
                > Connecting to Bitget WebSocket... [OK]<br>
                > Trinity Protocol... ACTIVE<br>
                > Awaiting market data...<br>
            </div>
        </div>
    </div>

    <script>
        // Simple script to make the terminal look alive
        const terminal = document.getElementById('sys-log');
        const logs = [
            "> SQUADRA_ALPHA: Scalp execution filled @ $64,320",
            "> ORACLE: Sentiment shifted +2 points",
            "> STROZZINO: Funding rate adjusted on Bybit",
            "> WHALE TRACKER: Alert - 10k ETH moved to cold storage",
            "> SQUADRA_DELTA: Order book imbalance neutralized"
        ];
        
        setInterval(() => {
            if (Math.random() > 0.6) {
                const logLine = document.createElement('div');
                logLine.textContent = logs[Math.floor(Math.random() * logs.length)] + " [" + new Date().toLocaleTimeString() + "]";
                terminal.appendChild(logLine);
                terminal.scrollTop = terminal.scrollHeight;
            }
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
