from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌌</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --bg-base: #020204;
            --neon-green: #00ffcc;
            --neon-red: #ff0055;
            --neon-purple: #b800e6;
            --neon-blue: #0088ff;
            --grid-color: rgba(0, 255, 204, 0.05);
            --scanline: rgba(0, 255, 204, 0.1);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-base);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            text-transform: uppercase;
        }

        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,0.3) 51%);
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 999;
        }

        .crt-flicker {
            animation: flicker 0.15s infinite;
        }

        @keyframes flicker {
            0% { opacity: 0.95; }
            50% { opacity: 1; }
            100% { opacity: 0.98; }
        }

        h1 {
            text-align: center;
            font-size: 2.8rem;
            color: #fff;
            text-shadow: 
                0 0 5px #fff,
                0 0 10px #fff,
                0 0 20px var(--neon-green),
                0 0 40px var(--neon-green),
                0 0 80px var(--neon-green);
            margin-bottom: 5px;
            letter-spacing: 4px;
        }

        .sys-status {
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 40px;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(2, 2, 4, 0.85);
            border: 1px solid var(--neon-green);
            padding: 25px;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0, 255, 204, 0.1), 0 0 15px rgba(0, 255, 204, 0.2);
            backdrop-filter: blur(5px);
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
        }

        .panel.red {
            border-color: var(--neon-red);
            box-shadow: inset 0 0 20px rgba(255, 0, 85, 0.1), 0 0 15px rgba(255, 0, 85, 0.2);
        }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); border-bottom-color: var(--neon-red); }

        .panel.purple {
            border-color: var(--neon-purple);
            box-shadow: inset 0 0 20px rgba(184, 0, 230, 0.1), 0 0 15px rgba(184, 0, 230, 0.2);
        }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 15px var(--neon-purple); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); border-bottom-color: var(--neon-purple); }

        .panel.blue {
            border-color: var(--neon-blue);
            box-shadow: inset 0 0 20px rgba(0, 136, 255, 0.1), 0 0 15px rgba(0, 136, 255, 0.2);
        }
        .panel.blue::before { background: var(--neon-blue); box-shadow: 0 0 15px var(--neon-blue); }
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom-color: var(--neon-blue); }

        h2 {
            margin-top: 0;
            font-size: 1.5rem;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .squad-list, .trinity-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .squad-list li, .trinity-list li {
            margin-bottom: 15px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.03);
            border-left: 4px solid var(--neon-green);
            position: relative;
            transition: all 0.3s ease;
        }

        .panel.red .squad-list li { border-left-color: var(--neon-red); }
        .panel.purple .trinity-list li { border-left-color: var(--neon-purple); }

        .squad-list li:hover, .trinity-list li:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(5px);
        }

        .title-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-weight: bold;
            font-size: 1.1rem;
        }

        .details {
            font-size: 0.9rem;
            opacity: 0.8;
            line-height: 1.4;
        }

        .blinking-dot {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #0f0;
            box-shadow: 0 0 10px #0f0;
            animation: pulse 1.5s infinite;
        }
        .blinking-dot.red { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); animation: pulse-fast 0.8s infinite; }
        .blinking-dot.purple { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
        @keyframes pulse-fast { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }

        .market-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }

        .data-box {
            border: 1px solid rgba(0, 136, 255, 0.3);
            background: rgba(0, 136, 255, 0.05);
            padding: 15px;
            text-align: center;
        }

        .data-box .label {
            font-size: 0.8rem;
            color: rgba(0, 136, 255, 0.8);
            margin-bottom: 5px;
        }

        .data-box .value {
            font-size: 1.4rem;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue);
        }

        .terminal-log {
            font-size: 0.85rem;
            background: rgba(0,0,0,0.5);
            padding: 15px;
            border: 1px solid var(--neon-blue);
            height: 150px;
            overflow: hidden;
            color: var(--neon-blue);
        }

        .log-line {
            margin-bottom: 5px;
            opacity: 0;
            animation: fadeIn 0.5s forwards;
        }

        @keyframes fadeIn { to { opacity: 1; } }
        
        /* Decorative scanner */
        .radar {
            position: absolute;
            top: 10px; right: 10px;
            width: 40px; height: 40px;
            border: 1px solid var(--neon-green);
            border-radius: 50%;
            overflow: hidden;
        }
        .panel.red .radar { border-color: var(--neon-red); }
        .panel.purple .radar { border-color: var(--neon-purple); }
        .radar::after {
            content: '';
            position: absolute;
            top: 50%; left: 50%;
            width: 50%; height: 50%;
            background: linear-gradient(45deg, transparent, rgba(255,255,255,0.8));
            transform-origin: top left;
            animation: spin 2s linear infinite;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }

    </style>
</head>
<body class="crt-flicker">
    <div class="scanlines"></div>

    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <div class="sys-status">
        [ SYSTEM UPLINK SECURE ] // LOCAL TIME: <span id="clock">--:--:--</span> // ENCRYPTION: AES-256<br>
        <span style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel red">
            <div class="radar"></div>
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul class="squad-list">
                <li>
                    <div class="title-row">
                        <span>SQUADRA_ALPHA</span>
                        <span class="blinking-dot red"></span>
                    </div>
                    <div class="details">
                        > ROLE: Scalper<br>
                        > ZONE: Binance Spot<br>
                        > LATENCY: 12ms | WINRATE: 68%
                    </div>
                </li>
                <li>
                    <div class="title-row">
                        <span>SQUADRA_DELTA</span>
                        <span class="blinking-dot red"></span>
                    </div>
                    <div class="details">
                        > ROLE: Order Flow & Imbalance<br>
                        > ZONE: CME / Deribit<br>
                        > LOAD: 89% | ALPHA DETECTED
                    </div>
                </li>
                <li>
                    <div class="title-row">
                        <span>SQUADRA_GAMMA</span>
                        <span class="blinking-dot red"></span>
                    </div>
                    <div class="details">
                        > ROLE: Pairs Trading<br>
                        > ZONE: Bitget Futures<br>
                        > SPREAD: 0.04% | STATUS: ENGAGED
                    </div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <div class="radar"></div>
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul class="trinity-list">
                <li>
                    <div class="title-row">
                        <span>🦇 LO STROZZINO</span>
                        <span class="blinking-dot purple"></span>
                    </div>
                    <div class="details">
                        > ROLE: Funding Rate Arbitrage<br>
                        > TARGET: Perpetual Swaps<br>
                        > YIELD: +18.4% APY (Harvesting)
                    </div>
                </li>
                <li>
                    <div class="title-row">
                        <span>🧮 IL CONTABILE</span>
                        <span class="blinking-dot purple"></span>
                    </div>
                    <div class="details">
                        > ROLE: Smart DCA & Rebalancing<br>
                        > ASSETS: BTC, ETH, SOL<br>
                        > NEXT EXECUTION: T-Minus 04:00:00
                    </div>
                </li>
                <li>
                    <div class="title-row">
                        <span>🛡️ L'ANGELO CUSTODE</span>
                        <span class="blinking-dot purple"></span>
                    </div>
                    <div class="details">
                        > ROLE: MEV Protection & Sniper<br>
                        > ZONE: Arbitrum One / Base<br>
                        > TX SENT: 1,402 | BLOCKS WON: 89
                    </div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="market-grid">
                <div class="data-box">
                    <div class="label">👁️ THE ORACLE (BINANCE)</div>
                    <div class="value" style="color: #0f0; text-shadow: 0 0 10px #0f0;">BULLISH (87%)</div>
                </div>
                <div class="data-box">
                    <div class="label">🐋 WHALE TRACKER</div>
                    <div class="value" style="color: #ff0055; text-shadow: 0 0 10px #ff0055;">ALERT</div>
                </div>
                <div class="data-box">
                    <div class="label">📊 GLOBAL VOLATILITY</div>
                    <div class="value">ELEVATED</div>
                </div>
                <div class="data-box">
                    <div class="label">💻 CORE LOAD</div>
                    <div class="value">14.2%</div>
                </div>
            </div>

            <div class="terminal-log" id="terminal">
                <div class="log-line">> INITIALIZING MARKET SCANNERS...</div>
                <div class="log-line">> CONNECTING TO BINANCE WEBSOCKET... OK.</div>
                <div class="log-line">> CONNECTING TO DERIBIT FIX... OK.</div>
                <div class="log-line">> LISTENING FOR MEMPOOL EVENTS...</div>
            </div>
        </div>
    </div>

    <script>
        // Clock
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString().replace('T', ' ').substr(0, 19) + ' UTC';
        }, 1000);

        // Fake terminal logs for Whale Tracker / Oracle
        const logs = [
            "[WHALE] 5,000 BTC moved to Coinbase (Tx: 0x4a9...)",
            "[ORACLE] RSI Divergence detected on ETH/USDT 15m",
            "[SYSTEM] Rebalancing Il Contabile buffers...",
            "[MEV] Block 1490281 secured by L'Angelo Custode",
            "[HFT] SQUADRA_ALPHA executed 450 trades in 60s",
            "[WHALE] Stablecoin inflow spike detected on ERC20",
            "[ORACLE] Sentiment shifting to NEUTRAL on SOL",
            "[FUNDING] Lo Strozzino locked 0.02% spread on Bybit"
        ];
        
        const terminal = document.getElementById('terminal');
        setInterval(() => {
            const newLine = document.createElement('div');
            newLine.className = 'log-line';
            newLine.innerText = '> ' + logs[Math.floor(Math.random() * logs.length)];
            terminal.appendChild(newLine);
            if (terminal.childElementCount > 6) {
                terminal.removeChild(terminal.firstChild);
            }
        }, 3500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
