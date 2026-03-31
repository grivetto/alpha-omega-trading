import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

# Template HTML con stile Cyberpunk / Neon molto dettagliato
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@500;700&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff003c;
            --neon-green: #39ff14;
            --neon-red: #ff2a2a;
            --neon-yellow: #fcee0a;
            --bg-color: #030305;
            --panel-bg: rgba(5, 10, 15, 0.75);
            --border-color: rgba(0, 243, 255, 0.4);
            --scanline: rgba(0, 243, 255, 0.05);
        }
        
        * { box-sizing: border-box; }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vh 2vw;
            background-image: 
                linear-gradient(var(--scanline) 1px, transparent 1px),
                linear-gradient(90deg, var(--scanline) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3, .title {
            font-family: 'Orbitron', sans-serif;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue);
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            border: 1px solid var(--neon-blue);
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.2), 0 0 15px rgba(0, 243, 255, 0.4);
            background: repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(0, 243, 255, 0.05) 10px, rgba(0, 243, 255, 0.05) 20px);
            position: relative;
        }

        .header::before, .header::after {
            content: '[ O C ]';
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            color: var(--neon-pink);
            font-size: 1.5em;
            text-shadow: 0 0 10px var(--neon-pink);
        }
        .header::before { left: 20px; }
        .header::after { right: 20px; }

        .glitch {
            animation: glitch 1.5s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,.75), -0.05em -0.025em 0 rgba(0,255,0,.75), -0.025em 0.05em 0 rgba(0,0,255,.75); }
            14% { text-shadow: 0.05em 0 0 rgba(255,0,0,.75), -0.05em -0.025em 0 rgba(0,255,0,.75), -0.025em 0.05em 0 rgba(0,0,255,.75); }
            15% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,.75), 0.025em 0.025em 0 rgba(0,255,0,.75), -0.05em -0.05em 0 rgba(0,0,255,.75); }
            49% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,.75), 0.025em 0.025em 0 rgba(0,255,0,.75), -0.05em -0.05em 0 rgba(0,0,255,.75); }
            50% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,.75), 0.05em 0 0 rgba(0,255,0,.75), 0 -0.05em 0 rgba(0,0,255,.75); }
            99% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,.75), 0.05em 0 0 rgba(0,255,0,.75), 0 -0.05em 0 rgba(0,0,255,.75); }
            100% { text-shadow: -0.025em 0 0 rgba(255,0,0,.75), -0.025em -0.025em 0 rgba(0,255,0,.75), -0.025em -0.05em 0 rgba(0,0,255,.75); }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            z-index: 10;
            position: relative;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 0, 0, 0.8);
            position: relative;
        }

        .panel.alert { border-color: var(--neon-pink); box-shadow: inset 0 0 20px rgba(255,0,60,0.15), 0 0 10px rgba(255,0,60,0.3); }
        .panel.alert h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        
        .panel.trinity { border-color: var(--neon-green); box-shadow: inset 0 0 20px rgba(57,255,20,0.1), 0 0 10px rgba(57,255,20,0.2); }
        .panel.trinity h2 { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 15px; height: 15px;
            border-top: 2px solid var(--neon-blue); border-left: 2px solid var(--neon-blue);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 15px; height: 15px;
            border-bottom: 2px solid var(--neon-blue); border-right: 2px solid var(--neon-blue);
        }
        .panel.alert::before, .panel.alert::after { border-color: var(--neon-pink); }
        .panel.trinity::before, .panel.trinity::after { border-color: var(--neon-green); }

        .status-dot {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite alternate;
        }
        .status-dot.standby { background-color: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); }
        .status-dot.offline { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        @keyframes pulse { 0% { opacity: 0.5; box-shadow: 0 0 5px; } 100% { opacity: 1; box-shadow: 0 0 15px; } }

        .list-item {
            margin-bottom: 15px;
            padding: 12px;
            background: rgba(0,0,0,0.6);
            border-left: 4px solid var(--neon-blue);
            transition: all 0.3s ease;
        }
        .list-item:hover {
            background: rgba(0,243,255,0.1);
            border-left-color: var(--neon-pink);
            transform: scale(1.02);
        }
        .panel.alert .list-item { border-left-color: var(--neon-pink); }
        .panel.trinity .list-item { border-left-color: var(--neon-green); }

        .metric-row { display: flex; justify-content: space-between; border-bottom: 1px dotted rgba(255,255,255,0.2); padding: 6px 0; margin-top: 5px; }
        .metric-value { font-weight: bold; }
        .val-up { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .val-down { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .val-neutral { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }

        .bar-container { width: 100%; background: #111; height: 10px; margin-top: 5px; border: 1px solid #333; position: relative; }
        .bar-fill { height: 100%; background: var(--neon-blue); width: 0%; transition: width 0.5s; box-shadow: 0 0 10px var(--neon-blue); }

        .terminal {
            background: #000;
            color: var(--neon-green);
            padding: 15px;
            border: 1px solid var(--neon-green);
            font-size: 0.9em;
            height: 200px;
            overflow-y: hidden;
            box-shadow: inset 0 0 20px rgba(0,255,0,0.1);
            position: relative;
        }
        .terminal-line { margin: 3px 0; }
        .terminal-line::before { content: "> "; opacity: 0.5; }

        .crosshair {
            position: absolute; width: 40px; height: 40px;
            border: 1px solid rgba(255,0,60,0.3); pointer-events: none;
            animation: rotate 10s linear infinite;
            top: 10px; right: 10px;
        }
        .crosshair::before { content: ''; position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: rgba(255,0,60,0.5); }
        .crosshair::after { content: ''; position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: rgba(255,0,60,0.5); }
        @keyframes rotate { 100% { transform: rotate(360deg); } }

        .footer { text-align: center; margin-top: 30px; font-size: 0.8em; color: rgba(0,243,255,0.4); border-top: 1px solid rgba(0,243,255,0.2); padding-top: 10px;}
    </style>
</head>
<body>

    <div class="header glitch">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>[ CENTRAL QUANTITATIVE HFT SYSTEM - MILITARY GRADE ]</p>
        <p style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 10px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel alert">
            <div class="crosshair"></div>
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="list-item">
                <div class="title"><span class="status-dot"></span> <b>SQUADRA_ALPHA</b> <span style="font-size:0.7em; color:var(--neon-pink);">[ENGAGED]</span></div>
                <div style="font-size:0.8em; color:#888;">Binance Scalper | Target: BTC/USDT</div>
                <div class="metric-row"><span>Execution Latency:</span> <span class="metric-value" id="alpha-lat">12ms</span></div>
                <div class="metric-row"><span>Win Rate (1h):</span> <span class="metric-value val-up">68.4%</span></div>
                <div class="bar-container"><div class="bar-fill" style="background:var(--neon-pink); width:68.4%;"></div></div>
            </div>

            <div class="list-item">
                <div class="title"><span class="status-dot standby"></span> <b>SQUADRA_DELTA</b> <span style="font-size:0.7em; color:var(--neon-yellow);">[SCANNING]</span></div>
                <div style="font-size:0.8em; color:#888;">Order Flow & Spoofing Detection | ETH/USDT</div>
                <div class="metric-row"><span>Orderbook Imbalance:</span> <span class="metric-value val-neutral" id="delta-imb">-4.2%</span></div>
                <div class="metric-row"><span>Spoofing Alerts:</span> <span class="metric-value val-down">2 ACTIVE</span></div>
            </div>

            <div class="list-item">
                <div class="title"><span class="status-dot"></span> <b>SQUADRA_GAMMA</b> <span style="font-size:0.7em; color:var(--neon-blue);">[ENGAGED]</span></div>
                <div style="font-size:0.8em; color:#888;">Pairs Trading | Bitget L1 vs L2</div>
                <div class="metric-row"><span>Current Spread:</span> <span class="metric-value val-up" id="gamma-spread">+1.05%</span></div>
                <div class="metric-row"><span>Z-Score:</span> <span class="metric-value val-up">2.41 σ</span></div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>💠 PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; border: 1px solid var(--neon-green); background: rgba(57,255,20,0.05); text-align: center; text-shadow: 0 0 5px var(--neon-green);">
                SYSTEM STATUS: BACKGROUND PROCESSES ACTIVE
            </div>

            <div class="list-item">
                <div class="title"><span class="status-dot"></span> <b>LO STROZZINO</b> <span style="font-size:0.7em;">[ONLINE]</span></div>
                <div style="font-size:0.8em; color:#888;">Funding Arb (Spot vs Perp) | Aggressive</div>
                <div class="metric-row"><span>Aggregated APR:</span> <span class="metric-value val-up" id="strozzino-apr">22.4%</span></div>
                <div class="metric-row"><span>Capital Deployed:</span> <span class="metric-value">$45,200</span></div>
            </div>

            <div class="list-item">
                <div class="title"><span class="status-dot"></span> <b>IL CONTABILE</b> <span style="font-size:0.7em;">[ONLINE]</span></div>
                <div style="font-size:0.8em; color:#888;">Smart DCA | Target: Altcoins Top 20</div>
                <div class="metric-row"><span>Next Execution in:</span> <span class="metric-value val-neutral">02:14:33</span></div>
                <div class="metric-row"><span>Dip Threshold:</span> <span class="metric-value val-down">-15.0%</span></div>
            </div>

            <div class="list-item">
                <div class="title"><span class="status-dot"></span> <b>L'ANGELO CUSTODE</b> <span style="font-size:0.7em;">[ONLINE]</span></div>
                <div style="font-size:0.8em; color:#888;">MEV Arbitrum | Sandwich & Backrun Protection</div>
                <div class="metric-row"><span>Blocks Sniped (24h):</span> <span class="metric-value val-up">142</span></div>
                <div class="metric-row"><span>Total Value Saved:</span> <span class="metric-value val-up">3.4 ETH</span></div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 MARKET INTELLIGENCE</h2>

            <div class="list-item">
                <div class="title">👁️ THE ORACLE</div>
                <div style="font-size:0.8em; color:#888;">Binance Sentiment & NLP AI Analysis</div>
                <div class="metric-row"><span>Index Score:</span> <span class="metric-value val-up" id="oracle-score">82 [EXTREME GREED]</span></div>
                <div class="bar-container"><div class="bar-fill" style="background:var(--neon-green); width:82%;"></div></div>
            </div>

            <div class="list-item">
                <div class="title">🐋 WHALE TRACKER</div>
                <div style="font-size:0.8em; color:#888;">On-Chain Net Flow & Big Order Blocks</div>
                <div class="metric-row"><span>Net Flow (1h):</span> <span class="metric-value val-down" id="whale-flow">-$12.4M [OUTFLOW]</span></div>
                <div class="metric-row"><span>Block Alerts:</span> <span class="metric-value val-down">5 DETECTED</span></div>
            </div>

            <h3 style="margin-top:20px; font-size:1em; border-bottom:1px solid var(--neon-blue); padding-bottom:5px;">TERMINAL LOGS</h3>
            <div class="terminal" id="terminal">
                <div class="terminal-line">SYSTEM INITIALIZED. ORBITAL COMMAND V3.0</div>
                <div class="terminal-line">CONNECTING TO SECURE SOCKETS... OK</div>
            </div>
        </div>
    </div>

    <div class="footer">
        © 2026 NUVOLA CAPITAL // SECURE ENCLAVE ACTIVE // UNAUTHORIZED ACCESS WILL BE TERMINATED.
    </div>

    <script>
        // Simulazione aggiornamenti dati
        setInterval(() => {
            document.getElementById('alpha-lat').innerText = Math.floor(Math.random() * 5 + 10) + 'ms';
            document.getElementById('delta-imb').innerText = (Math.random() * 10 - 5).toFixed(2) + '%';
            document.getElementById('gamma-spread').innerText = '+' + (Math.random() * 2 + 0.5).toFixed(2) + '%';
            document.getElementById('strozzino-apr').innerText = (Math.random() * 5 + 20).toFixed(1) + '%';
        }, 1500);

        // Simulazione Terminal Logs
        const logMessages = [
            "[HFT-ALPHA] Executed LIMIT BUY 0.5 BTC @ 64,102.50",
            "[HFT-DELTA] Warning: Spoofing detected on ETH orderbook. Cancelling orders.",
            "[HFT-GAMMA] Rebalancing SOL/ETH pair hedge.",
            "[TRINITY-STROZZINO] Collecting funding fees on Bybit Perp (+0.015%).",
            "[TRINITY-CUSTODE] Front-running malicious sandwich bot on Arbitrum DEX.",
            "[ORACLE] Twitter NLP sentiment shifted +5% bullish in last 10m.",
            "[WHALE] Alert: 2000 ETH transferred from unknown wallet to Binance.",
            "[SYS] Neural latency check: 14ms average."
        ];

        const terminal = document.getElementById('terminal');
        setInterval(() => {
            const newLine = document.createElement('div');
            newLine.className = 'terminal-line';
            newLine.innerText = logMessages[Math.floor(Math.random() * logMessages.length)];
            terminal.appendChild(newLine);
            if (terminal.children.length > 8) {
                terminal.removeChild(terminal.firstChild);
            }
            terminal.scrollTop = terminal.scrollHeight;
        }, 2200);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue sulla porta 5000 in tutte le interfacce
    app.run(host='0.0.0.0', port=5000, debug=False)
