import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

# Template HTML con stile Cyberpunk / Neon
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #0f0;
            --neon-red: #f00;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 30, 0.85);
            --border-color: rgba(0, 255, 255, 0.3);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 20px -10px var(--neon-blue);
            animation: pulse 2s infinite alternate;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-blue); }
            100% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1), 0 0 10px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .status-dot {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
        }

        .status-dot.offline { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .status-dot.standby { background-color: var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); }

        ul { list-style-type: none; padding: 0; }
        li {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0,0,0,0.5);
            border-left: 3px solid var(--neon-blue);
            transition: all 0.3s ease;
        }
        li:hover {
            border-left-color: var(--neon-pink);
            transform: translateX(5px);
            box-shadow: inset 50px 0 50px -50px var(--neon-pink);
        }

        .metric-row { display: flex; justify-content: space-between; border-bottom: 1px dashed rgba(0,255,255,0.2); padding: 5px 0; }
        .metric-value { color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 5px var(--neon-pink); }

        .terminal {
            background: #000;
            color: #0f0;
            padding: 15px;
            border: 1px solid #0f0;
            border-radius: 3px;
            font-size: 0.9em;
            height: 150px;
            overflow-y: hidden;
            box-shadow: 0 0 10px rgba(0,255,0,0.2);
            position: relative;
        }
        
        .terminal-line { margin: 5px 0; animation: typing 0.5s steps(40, end); }

        .footer { text-align: center; margin-top: 40px; font-size: 0.8em; color: rgba(0,255,255,0.5); }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <p>[ SISTEMA CENTRALE DI CONTROLLO HFT QUANTITATIVO - V3.0 ]</p>
    </div>

    <div class="grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div><span class="status-dot"></span> <b>SQUADRA_ALPHA</b> [Scalper Binance]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Target: BTC/USDT, ETH/USDT | Latenza: 12ms</div>
                    <div class="metric-row"><span>Trades/min:</span> <span class="metric-value">42</span></div>
                </li>
                <li>
                    <div><span class="status-dot standby"></span> <b>SQUADRA_DELTA</b> [Order Flow]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Analisi Liquidity Pools & Spoofing Detection</div>
                    <div class="metric-row"><span>Status:</span> <span class="metric-value" style="color:var(--neon-pink);">ANALISI IN CORSO...</span></div>
                </li>
                <li>
                    <div><span class="status-dot"></span> <b>SQUADRA_GAMMA</b> [Pairs Trading Bitget]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Cointegration Arb: L1 vs L2 Tokens</div>
                    <div class="metric-row"><span>Spread Arb:</span> <span class="metric-value">+1.24%</span></div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>💠 PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(0,255,0,0.1); color: var(--neon-green); text-align: center; font-weight: bold; text-shadow: 0 0 5px var(--neon-green); border-radius: 3px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <ul>
                <li>
                    <div><span class="status-dot"></span> <b>LO STROZZINO</b> [Funding Arb]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Spot vs Perp Arbitrage sui mercati Degen</div>
                    <div class="metric-row"><span>Yield Stimato (APR):</span> <span class="metric-value">34.5%</span></div>
                </li>
                <li>
                    <div><span class="status-dot"></span> <b>IL CONTABILE</b> [Smart DCA]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Accumulo aggressivo su ritracciamenti > 15%</div>
                    <div class="metric-row"><span>Fondi Allocati:</span> <span class="metric-value">$12,450.00</span></div>
                </li>
                <li>
                    <div><span class="status-dot"></span> <b>L'ANGELO CUSTODE</b> [MEV Arbitrum]</div>
                    <div style="font-size:0.8em; color:gray; margin-top:5px;">Sandwich & Backrun Protections Dex Aggregators</div>
                    <div class="metric-row"><span>Tx Salvate:</span> <span class="metric-value">1,402</span></div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 THE ORACLE & METRICHE</h2>
            <div style="margin-bottom: 15px;">
                <div class="metric-row"><span>👁️ Binance Sentiment Index:</span> <span class="metric-value">EXTREME GREED (88)</span></div>
                <div class="metric-row"><span>🐋 Whale Tracker Alarms (1h):</span> <span class="metric-value">14 Trovati</span></div>
                <div class="metric-row"><span>⚡ Rete Arbitrum Gas:</span> <span class="metric-value">0.012 Gwei</span></div>
                <div class="metric-row"><span>🔥 PnL Giornaliero Stimato:</span> <span class="metric-value" style="color:var(--neon-green);">+$420.69</span></div>
            </div>
            
            <h3>> SYSTEM LOGS _</h3>
            <div class="terminal">
                <div class="terminal-line">[SYS] Connessione a WebSocket Binance... OK</div>
                <div class="terminal-line">[HFT] SQUADRA_ALPHA ordine eseguito a 64,210.50 USDT</div>
                <div class="terminal-line">[MEV] Angelo Custode bypassa mempool congestion...</div>
                <div class="terminal-line">[SYS] Heartbeat SQUADRA_GAMMA ricevuto. Latency 24ms.</div>
                <div class="terminal-line blink" style="color:var(--neon-pink);">[WARN] Whale spotted moving 5000 ETH to Coinbase...</div>
            </div>
        </div>
    </div>

    <div class="footer">
        © 2026 NUVOLA CAPITAL. RESTRICTED ACCESS. UNAUTHORIZED CONNECTIONS WILL BE TRACED AND TERMINATED.
    </div>

    <script>
        // Effetto blink per il warning nel terminale
        setInterval(() => {
            const warn = document.querySelector('.blink');
            if(warn) warn.style.opacity = warn.style.opacity === '0' ? '1' : '0';
        }, 500);
        
        // Simula log dinamici
        const logs = [
            "[HFT] Scalping micro-profit: +0.02%",
            "[SYS] Rebalancing pool liquidity...",
            "[TRINITY] Lo Strozzino ha incassato funding rate 0.01%",
            "[WARN] Elevata volatilità rilevata su SOL/USDT",
            "[HFT] Ping server Tokyo: 145ms. Switching to Frankfurt (18ms)..."
        ];
        const terminal = document.querySelector('.terminal');
        setInterval(() => {
            const newLine = document.createElement('div');
            newLine.className = 'terminal-line';
            newLine.textContent = logs[Math.floor(Math.random() * logs.length)];
            terminal.appendChild(newLine);
            if(terminal.children.length > 6) {
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
    # Esegue sulla porta 5000
    app.run(host='0.0.0.0', port=5000, debug=False)