import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@500;700;900&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff003c;
            --neon-green: #39ff14;
            --neon-red: #ff2a2a;
            --neon-yellow: #fcee0a;
            --bg-color: #010102;
            --panel-bg: rgba(5, 10, 15, 0.85);
            --border-color: rgba(0, 243, 255, 0.5);
            --scanline: rgba(0, 243, 255, 0.08);
            --grid-line: rgba(0, 243, 255, 0.1);
        }
        
        * { box-sizing: border-box; }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 2vh 2vw;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
            text-shadow: 0 0 2px rgba(0, 243, 255, 0.4);
        }

        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 100;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3, .title {
            font-family: 'Orbitron', sans-serif;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            letter-spacing: 3px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            border: 2px solid var(--neon-blue);
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: inset 0 0 30px rgba(0, 243, 255, 0.3), 0 0 20px rgba(0, 243, 255, 0.5);
            background: repeating-linear-gradient(45deg, rgba(0,0,0,0.8), rgba(0,0,0,0.8) 10px, rgba(0, 243, 255, 0.1) 10px, rgba(0, 243, 255, 0.1) 20px);
            position: relative;
        }

        .header::before, .header::after {
            content: '[\u26A1]';
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            color: var(--neon-pink);
            font-size: 2em;
            text-shadow: 0 0 15px var(--neon-pink), 0 0 30px var(--neon-pink);
        }
        .header::before { left: 30px; }
        .header::after { right: 30px; }

        .glitch {
            animation: glitch 2s infinite;
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
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 25px;
            z-index: 10;
            position: relative;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            box-shadow: inset 0 0 25px rgba(0, 243, 255, 0.15), 0 0 15px rgba(0, 0, 0, 0.9);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel.alert { border-color: var(--neon-pink); box-shadow: inset 0 0 30px rgba(255,0,60,0.2), 0 0 15px rgba(255,0,60,0.4); }
        .panel.alert h2 { color: var(--neon-pink); text-shadow: 0 0 15px var(--neon-pink); border-bottom: 2px solid var(--neon-pink); padding-bottom: 10px;}
        
        .panel.trinity { border-color: var(--neon-green); box-shadow: inset 0 0 30px rgba(57,255,20,0.15), 0 0 15px rgba(57,255,20,0.3); }
        .panel.trinity h2 { color: var(--neon-green); text-shadow: 0 0 15px var(--neon-green); border-bottom: 2px solid var(--neon-green); padding-bottom: 10px;}

        .panel.intel h2 { color: var(--neon-yellow); text-shadow: 0 0 15px var(--neon-yellow); border-bottom: 2px solid var(--neon-yellow); padding-bottom: 10px;}
        .panel.intel { border-color: var(--neon-yellow); box-shadow: inset 0 0 30px rgba(252,238,10,0.15), 0 0 15px rgba(252,238,10,0.3); }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; width: 25px; height: 25px;
            border-top: 3px solid var(--neon-blue); border-left: 3px solid var(--neon-blue);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: -2px; right: -2px; width: 25px; height: 25px;
            border-bottom: 3px solid var(--neon-blue); border-right: 3px solid var(--neon-blue);
        }
        .panel.alert::before, .panel.alert::after { border-color: var(--neon-pink); }
        .panel.trinity::before, .panel.trinity::after { border-color: var(--neon-green); }
        .panel.intel::before, .panel.intel::after { border-color: var(--neon-yellow); }

        .status-dot {
            display: inline-block;
            width: 12px; height: 12px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
            margin-right: 12px;
            animation: pulse 1s infinite alternate;
        }
        .status-dot.standby { background-color: var(--neon-yellow); box-shadow: 0 0 15px var(--neon-yellow); animation: pulse 2s infinite alternate;}
        .status-dot.offline { background-color: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); animation: none;}

        @keyframes pulse { 0% { opacity: 0.3; box-shadow: 0 0 2px; } 100% { opacity: 1; box-shadow: 0 0 20px; } }

        .list-item {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.7);
            border-left: 5px solid var(--neon-blue);
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }
        .list-item::after {
            content: "";
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent);
            transform: skewX(-20deg);
            animation: scan 4s infinite;
        }
        @keyframes scan {
            0% { left: -100%; }
            20% { left: 200%; }
            100% { left: 200%; }
        }

        .list-item:hover {
            background: rgba(0,243,255,0.15);
            border-left-color: var(--neon-pink);
            transform: translateX(5px);
        }
        .panel.alert .list-item { border-left-color: var(--neon-pink); }
        .panel.trinity .list-item { border-left-color: var(--neon-green); }
        .panel.intel .list-item { border-left-color: var(--neon-yellow); }

        .metric-row { display: flex; justify-content: space-between; border-bottom: 1px dotted rgba(255,255,255,0.1); padding: 8px 0; margin-top: 5px; font-size: 0.95em;}
        .metric-value { font-weight: bold; letter-spacing: 1px;}
        .val-up { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }
        .val-down { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .val-neutral { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        .bar-container { width: 100%; background: #0a0a0a; height: 12px; margin-top: 10px; border: 1px solid #222; position: relative; overflow: hidden;}
        .bar-fill { height: 100%; background: var(--neon-blue); width: 0%; transition: width 0.3s ease-in-out; box-shadow: 0 0 15px var(--neon-blue); position: relative;}
        .bar-fill::after {
            content: "";
            position: absolute;
            top: 0; bottom: 0; right: 0; width: 5px; background: #fff; box-shadow: 0 0 10px #fff;
        }

        .terminal {
            background: #000;
            color: var(--neon-green);
            padding: 20px;
            border: 1px solid var(--neon-green);
            font-size: 0.9em;
            height: 250px;
            overflow-y: auto;
            box-shadow: inset 0 0 30px rgba(0,255,0,0.15);
            position: relative;
            scrollbar-width: thin;
            scrollbar-color: var(--neon-green) #000;
        }
        .terminal::-webkit-scrollbar { width: 8px; }
        .terminal::-webkit-scrollbar-track { background: #000; }
        .terminal::-webkit-scrollbar-thumb { background-color: var(--neon-green); }

        .terminal-line { margin: 5px 0; text-shadow: 0 0 5px var(--neon-green); }
        .terminal-line::before { content: "root@orbital:~# "; opacity: 0.7; color: #fff;}
        .terminal-line.error { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .terminal-line.error::before { content: "[!] "; color: var(--neon-pink); }
        .terminal-line.warn { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        .terminal-line.warn::before { content: "[*] "; color: var(--neon-yellow); }

        .crosshair {
            position: absolute; width: 50px; height: 50px;
            border: 1px solid rgba(255,0,60,0.5); pointer-events: none;
            animation: rotate 15s linear infinite;
            top: 20px; right: 20px;
        }
        .crosshair::before { content: ''; position: absolute; top: 50%; left: -10px; right: -10px; height: 1px; background: rgba(255,0,60,0.8); }
        .crosshair::after { content: ''; position: absolute; left: 50%; top: -10px; bottom: -10px; width: 1px; background: rgba(255,0,60,0.8); }
        @keyframes rotate { 100% { transform: rotate(360deg); } }

        .footer { text-align: center; margin-top: 40px; font-size: 0.9em; color: rgba(0,243,255,0.5); border-top: 1px solid rgba(0,243,255,0.3); padding-top: 20px; font-family: 'Orbitron', sans-serif;}
        
        .badge {
            display: inline-block;
            padding: 2px 6px;
            font-size: 0.7em;
            border: 1px solid currentColor;
            margin-left: 10px;
            vertical-align: middle;
            animation: blink 2s infinite;
        }
        @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0.5; } }
    </style>
</head>
<body>

    <div class="header glitch">
        <h1 style="font-size: 2.5em; margin-bottom: 5px;">🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p style="font-size: 1.2em; color: #aaa;">[ CENTRAL QUANTITATIVE HFT SYSTEM - MILITARY GRADE ]</p>
        <div style="display: inline-block; border: 1px solid var(--neon-green); padding: 5px 15px; background: rgba(57,255,20,0.1); margin-top: 10px;">
            <p style="color: var(--neon-green); font-weight: bold; text-shadow: 0 0 10px var(--neon-green); margin: 0; font-size: 1.1em;">
                <span class="status-dot" style="width:8px; height:8px;"></span> ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </p>
        </div>
    </div>

    <div class="grid">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel alert">
            <div class="crosshair"></div>
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="list-item">
                <div class="title">
                    <span class="status-dot"></span> <b>SQUADRA_ALPHA</b> 
                    <span class="badge" style="color:var(--neon-pink);">ENGAGED</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Binance Scalper | Target: BTC/USDT | Strategy: Micro-Momentum</div>
                <div class="metric-row"><span>Execution Latency:</span> <span class="metric-value" id="alpha-lat">12.4ms</span></div>
                <div class="metric-row"><span>Order Fill Rate:</span> <span class="metric-value val-up">99.1%</span></div>
                <div class="metric-row"><span>Win Rate (1h):</span> <span class="metric-value val-up">68.4%</span></div>
                <div class="bar-container"><div class="bar-fill" style="background:var(--neon-pink); width:68.4%;"></div></div>
            </div>

            <div class="list-item">
                <div class="title">
                    <span class="status-dot standby"></span> <b>SQUADRA_DELTA</b> 
                    <span class="badge" style="color:var(--neon-yellow);">SCANNING</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Order Flow & Spoofing Detection | ETH/USDT</div>
                <div class="metric-row"><span>Orderbook Imbalance:</span> <span class="metric-value val-neutral" id="delta-imb">-4.2%</span></div>
                <div class="metric-row"><span>Spoofing Alerts:</span> <span class="metric-value val-down" id="delta-spoof">2 ACTIVE</span></div>
                <div class="metric-row"><span>Toxicity Index:</span> <span class="metric-value val-neutral" id="delta-tox">0.45</span></div>
            </div>

            <div class="list-item">
                <div class="title">
                    <span class="status-dot"></span> <b>SQUADRA_GAMMA</b> 
                    <span class="badge" style="color:var(--neon-blue);">ENGAGED</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Pairs Trading | Bitget L1 vs L2 | Asset: SOL/ETH</div>
                <div class="metric-row"><span>Current Spread:</span> <span class="metric-value val-up" id="gamma-spread">+1.05%</span></div>
                <div class="metric-row"><span>Z-Score:</span> <span class="metric-value val-up" id="gamma-z">2.41 σ</span></div>
                <div class="metric-row"><span>Notional Exposure:</span> <span class="metric-value">$125,000</span></div>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>💠 PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 20px; padding: 12px; border: 1px solid var(--neon-green); background: rgba(57,255,20,0.05); text-align: center; text-shadow: 0 0 5px var(--neon-green); font-weight: bold; letter-spacing: 2px;">
                SYSTEM STATUS: BACKGROUND PROCESSES FULLY OPERATIONAL
            </div>

            <div class="list-item">
                <div class="title">
                    <span class="status-dot"></span> <b>LO STROZZINO</b> 
                    <span class="badge" style="color:var(--neon-green);">ONLINE</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Funding Arb (Spot vs Perp) | Aggressive Profile</div>
                <div class="metric-row"><span>Aggregated APR:</span> <span class="metric-value val-up" id="strozzino-apr">22.4%</span></div>
                <div class="metric-row"><span>Capital Deployed:</span> <span class="metric-value">$45,200</span></div>
                <div class="metric-row"><span>Next Payout:</span> <span class="metric-value val-neutral" id="strozzino-time">04:12:00</span></div>
            </div>

            <div class="list-item">
                <div class="title">
                    <span class="status-dot"></span> <b>IL CONTABILE</b> 
                    <span class="badge" style="color:var(--neon-green);">ONLINE</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Smart DCA | Target: Altcoins Top 20 | Logic: RSI Oversold</div>
                <div class="metric-row"><span>Next Execution in:</span> <span class="metric-value val-neutral">02:14:33</span></div>
                <div class="metric-row"><span>Dip Threshold:</span> <span class="metric-value val-down">-15.0%</span></div>
                <div class="metric-row"><span>Allocated Fiat:</span> <span class="metric-value">$12,500</span></div>
            </div>

            <div class="list-item">
                <div class="title">
                    <span class="status-dot"></span> <b>L'ANGELO CUSTODE</b> 
                    <span class="badge" style="color:var(--neon-green);">ONLINE</span>
                </div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► MEV Arbitrum | Sandwich & Backrun Protection Shield</div>
                <div class="metric-row"><span>Blocks Sniped (24h):</span> <span class="metric-value val-up" id="angelo-blocks">142</span></div>
                <div class="metric-row"><span>Total Value Saved:</span> <span class="metric-value val-up" id="angelo-eth">3.41 ETH</span></div>
                <div class="metric-row"><span>Gas Optimizations:</span> <span class="metric-value val-up">ACTIVE</span></div>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel intel">
            <h2>📊 MARKET INTELLIGENCE</h2>

            <div class="list-item">
                <div class="title">👁️ THE ORACLE</div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► Binance Sentiment & NLP AI Analysis (Real-time X/News)</div>
                <div class="metric-row"><span>Index Score:</span> <span class="metric-value val-up" id="oracle-score">82 [EXTREME GREED]</span></div>
                <div class="metric-row"><span>Momentum Vector:</span> <span class="metric-value val-up">+1.4% / hr</span></div>
                <div class="bar-container"><div class="bar-fill" id="oracle-bar" style="background:var(--neon-green); width:82%;"></div></div>
            </div>

            <div class="list-item">
                <div class="title">🐋 WHALE TRACKER</div>
                <div style="font-size:0.85em; color:#aaa; margin-top:5px; margin-bottom:10px;">► On-Chain Net Flow & Big Order Blocks (CEX Inflow/Outflow)</div>
                <div class="metric-row"><span>Net Flow (1h):</span> <span class="metric-value val-down" id="whale-flow">-$12.4M [OUTFLOW]</span></div>
                <div class="metric-row"><span>Block Alerts:</span> <span class="metric-value val-down" id="whale-alerts">5 DETECTED</span></div>
                <div class="metric-row"><span>Largest Tx:</span> <span class="metric-value val-neutral">4500 ETH -> Coinbase</span></div>
            </div>

            <h3 style="margin-top:25px; font-size:1.2em; border-bottom:1px solid var(--neon-yellow); padding-bottom:10px; color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow);">🖥️ TERMINAL UPLINK</h3>
            <div class="terminal" id="terminal">
                <div class="terminal-line">SYSTEM INITIALIZED. ORBITAL COMMAND V3.5_SECURE</div>
                <div class="terminal-line">CONNECTING TO BINANCE WEBSOCKET... OK</div>
                <div class="terminal-line">CONNECTING TO ARBITRUM RPC... OK</div>
                <div class="terminal-line">LOADING TRINITY MODULES [3/3]... SUCCESS</div>
            </div>
        </div>
    </div>

    <div class="footer">
        © 2026 NUVOLA CAPITAL // SECURE ENCLAVE ACTIVE // UNAUTHORIZED ACCESS WILL BE TERMINATED // QUANTITATIVE DIVISION
    </div>

    <script>
        // Simulazione aggiornamenti dati
        setInterval(() => {
            document.getElementById('alpha-lat').innerText = (Math.random() * 5 + 8).toFixed(1) + 'ms';
            document.getElementById('delta-imb').innerText = (Math.random() * 12 - 6).toFixed(2) + '%';
            document.getElementById('delta-tox').innerText = (Math.random() * 0.8 + 0.1).toFixed(2);
            document.getElementById('gamma-spread').innerText = '+' + (Math.random() * 1.5 + 0.5).toFixed(2) + '%';
            document.getElementById('gamma-z').innerText = (Math.random() * 1 + 1.8).toFixed(2) + ' σ';
            document.getElementById('strozzino-apr').innerText = (Math.random() * 8 + 18).toFixed(1) + '%';
            
            let oracle = Math.floor(Math.random() * 20 + 70);
            document.getElementById('oracle-score').innerText = oracle + ' [EXTREME GREED]';
            document.getElementById('oracle-bar').style.width = oracle + '%';
            
            if(Math.random() > 0.8) {
                document.getElementById('delta-spoof').innerText = Math.floor(Math.random() * 4) + ' ACTIVE';
            }
        }, 1200);

        // Simulazione Terminal Logs
        const logMessages = [
            {t: "[HFT-ALPHA] Executed LIMIT BUY 0.5 BTC @ Market", type: "normal"},
            {t: "[HFT-DELTA] Spoofing signature detected on ETH orderbook. Adjusting delta.", type: "warn"},
            {t: "[HFT-GAMMA] Rebalancing SOL/ETH pair hedge. Spread captured.", type: "normal"},
            {t: "[TRINITY-STROZZINO] Collecting funding fees on Bybit Perp (+0.015%).", type: "normal"},
            {t: "[TRINITY-CUSTODE] Front-running malicious sandwich bot on Arbitrum DEX. Saved 0.05 ETH.", type: "normal"},
            {t: "[ORACLE] Twitter NLP sentiment shifted +5% bullish in last 10m. Keyword: 'ETF'.", type: "normal"},
            {t: "[WHALE] ALERT: Large transfer of 2000 ETH from unknown wallet to Binance.", type: "warn"},
            {t: "[SYS] Latency spike detected on RPC endpoint. Switching to fallback node.", type: "error"},
            {t: "[CONTABILE] Market dip detected. RSI at 28. Preparing DCA execution.", type: "warn"},
            {t: "[SYS] Neural latency check: 14ms average. All systems nominal.", type: "normal"}
        ];

        const terminal = document.getElementById('terminal');
        setInterval(() => {
            const msg = logMessages[Math.floor(Math.random() * logMessages.length)];
            const newLine = document.createElement('div');
            newLine.className = 'terminal-line';
            if(msg.type !== 'normal') newLine.classList.add(msg.type);
            
            let time = new Date().toLocaleTimeString('en-US', { hour12: false });
            newLine.innerText = `[${time}] ${msg.t}`;
            
            terminal.appendChild(newLine);
            if (terminal.children.length > 20) {
                terminal.removeChild(terminal.firstChild);
            }
            terminal.scrollTop = terminal.scrollHeight;
        }, 1800);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
