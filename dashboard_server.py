from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-color: #050510;
            --text-color: #00ffcc;
            --alert-color: #ff0055;
            --warn-color: #ffcc00;
            --panel-bg: rgba(0, 255, 204, 0.05);
            --border-glow: 0 0 10px #00ffcc;
            --alert-glow: 0 0 15px #ff0055;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        h1 {
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 5px;
            text-shadow: 0 0 20px #00ffcc;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--text-color);
            padding-bottom: 10px;
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
            border: 1px solid var(--text-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--text-color), transparent);
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .panel-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            border-bottom: 1px dashed var(--text-color);
            padding-bottom: 5px;
            text-transform: uppercase;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            align-items: center;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--text-color);
            box-shadow: 0 0 8px var(--text-color);
            animation: pulse 1.5s infinite alternate;
        }

        .status-alert {
            background-color: var(--alert-color);
            box-shadow: var(--alert-glow);
        }

        .status-warn {
            background-color: var(--warn-color);
            box-shadow: 0 0 8px var(--warn-color);
        }

        @keyframes pulse {
            0% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }

        .data-cell {
            background: rgba(0, 0, 0, 0.5);
            padding: 8px;
            border: 1px solid rgba(0, 255, 204, 0.3);
        }

        .data-label {
            color: #888;
            font-size: 0.8em;
            margin-bottom: 3px;
        }

        .data-value {
            font-weight: bold;
        }

        .terminal {
            background: #000;
            border: 1px solid var(--text-color);
            padding: 10px;
            font-size: 0.85em;
            height: 150px;
            overflow-y: hidden;
            color: #0f0;
            position: relative;
        }
        
        .terminal-line {
            margin: 2px 0;
            opacity: 0;
            animation: fadeIn 0.1s forwards;
        }
        
        @keyframes fadeIn {
            to { opacity: 1; }
        }
        
        /* CRT Effect overlay */
        .crt::before {
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

    </style>
</head>
<body class="crt">

    <h1>🛰️ ORBITAL COMMAND // NUVOLA ⚡</h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; border: 1px solid var(--text-color); padding: 10px; background: var(--panel-bg); text-shadow: var(--border-glow);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- ASSAULT TEAMS -->
        <div class="panel">
            <div class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</div>
            
            <div class="status-row">
                <span>🐺 SQUADRA_ALPHA [Binance Scalper]</span>
                <div><span class="status-indicator"></span> <span>ONLINE</span></div>
            </div>
            <div class="data-grid" style="margin-bottom: 15px;">
                <div class="data-cell"><div class="data-label">Win Rate</div><div class="data-value">68.4%</div></div>
                <div class="data-cell"><div class="data-label">Active Pos</div><div class="data-value">BTC/USDT (Long)</div></div>
            </div>

            <div class="status-row">
                <span>🎯 SQUADRA_DELTA [Order Flow]</span>
                <div><span class="status-indicator status-warn"></span> <span style="color: var(--warn-color)">WAITING</span></div>
            </div>
            <div class="data-grid" style="margin-bottom: 15px;">
                <div class="data-cell"><div class="data-label">Imbalance</div><div class="data-value">Buy Side Heavy</div></div>
                <div class="data-cell"><div class="data-label">Target</div><div class="data-value">ETH/USDT</div></div>
            </div>

            <div class="status-row">
                <span>⚖️ SQUADRA_GAMMA [Bitget Pairs]</span>
                <div><span class="status-indicator"></span> <span>ONLINE</span></div>
            </div>
            <div class="data-grid">
                <div class="data-cell"><div class="data-label">Spread Z-Score</div><div class="data-value">+2.45 (Shorting)</div></div>
                <div class="data-cell"><div class="data-label">Pair</div><div class="data-value">SOL/ADA</div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <div class="panel-title">🛡️ PROTOCOLLO TRINITY</div>
            
            <div class="status-row">
                <span>🧛 Lo Strozzino [Funding Arb]</span>
                <div><span class="status-indicator"></span> <span>ACTIVE</span></div>
            </div>
            <div class="data-grid" style="margin-bottom: 15px;">
                <div class="data-cell"><div class="data-label">APR Est.</div><div class="data-value">18.2%</div></div>
                <div class="data-cell"><div class="data-label">Capital Deployed</div><div class="data-value">$4,500</div></div>
            </div>

            <div class="status-row">
                <span>🧮 Il Contabile [DCA Engine]</span>
                <div><span class="status-indicator"></span> <span>IDLE</span></div>
            </div>
            <div class="data-grid" style="margin-bottom: 15px;">
                <div class="data-cell"><div class="data-label">Next Buy</div><div class="data-value">In 14h 22m</div></div>
                <div class="data-cell"><div class="data-label">Asset</div><div class="data-value">BTC</div></div>
            </div>

            <div class="status-row">
                <span>👼 L'Angelo Custode [MEV Arbitrum]</span>
                <div><span class="status-indicator status-alert"></span> <span style="color: var(--alert-color)">HUNTING</span></div>
            </div>
            <div class="data-grid">
                <div class="data-cell"><div class="data-label">Mempool Scan</div><div class="data-value">1420 tx/s</div></div>
                <div class="data-cell"><div class="data-label">Last Sniped</div><div class="data-value">2m ago (+0.04 ETH)</div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <div class="panel-title">👁️ THE ORACLE [Market Metrics]</div>
            
            <div class="data-grid" style="grid-template-columns: 1fr;">
                <div class="data-cell" style="display: flex; justify-content: space-between;">
                    <div class="data-label">Binance Global Sentiment</div>
                    <div class="data-value" style="color: #0f0;">BULLISH (72)</div>
                </div>
                <div class="data-cell" style="display: flex; justify-content: space-between;">
                    <div class="data-label">Whale Tracker (Large TXs)</div>
                    <div class="data-value" style="color: var(--alert-color);">DUMP WARNING</div>
                </div>
                <div class="data-cell" style="display: flex; justify-content: space-between;">
                    <div class="data-label">BTC Dominance</div>
                    <div class="data-value">54.2%</div>
                </div>
                <div class="data-cell" style="display: flex; justify-content: space-between;">
                    <div class="data-label">Fear & Greed Index</div>
                    <div class="data-value">GREED (68)</div>
                </div>
            </div>
            
            <div style="margin-top: 15px;">
                <div class="data-label" style="margin-bottom: 5px;">SYSTEM LOGS // CLASSIFIED</div>
                <div class="terminal" id="term">
                    <!-- Logs populated by JS -->
                </div>
            </div>
        </div>

    </div>

    <script>
        const logs = [
            "[SYSTEM] Initializing Orbital Command...",
            "[ORACLE] Connecting to Binance WebSocket...",
            "[ORACLE] Connection established. Latency: 12ms",
            "[ALPHA] Order placed: BUY 0.1 BTC @ MKT",
            "[ALPHA] Order filled. Trailing stop activated.",
            "[TRINITY] Lo Strozzino adjusting hedge ratio...",
            "[TRINITY] Hedge ratio optimal.",
            "[GAMMA] Calculating Z-Score for 50 pairs...",
            "[MEV] Scanning Arbitrum mempool...",
            "[MEV] Arbitrage opportunity detected (DEX route)",
            "[MEV] Executing flashbot bundle...",
            "[SYSTEM] Memory usage: 42% | CPU: 18%",
            "[WHALE] Alert: 5000 BTC moved to Coinbase"
        ];
        
        const term = document.getElementById('term');
        let i = 0;
        
        function addLog() {
            const line = document.createElement('div');
            line.className = 'terminal-line';
            line.innerText = `> ${logs[Math.floor(Math.random() * logs.length)]}`;
            term.appendChild(line);
            term.scrollTop = term.scrollHeight;
            
            if (term.children.length > 20) {
                term.removeChild(term.firstChild);
            }
            
            setTimeout(addLog, Math.random() * 2000 + 500);
        }
        
        setTimeout(addLog, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
