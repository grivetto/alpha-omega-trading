import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-green: #39ff14;
            --neon-red: #ff3333;
            --dark-bg: #030305;
            --panel-bg: rgba(5, 5, 10, 0.85);
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        body {
            background-color: var(--dark-bg);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 20px 20px;
            color: #e0e0e0;
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-transform: uppercase;
        }
        .crt::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-magenta);
            padding-bottom: 10px;
            animation: flicker 2s infinite alternate;
            margin-top: 0;
        }
        .header-bar {
            border: 1px solid var(--neon-magenta);
            padding: 15px;
            background: rgba(255, 0, 255, 0.1);
            border-radius: 5px;
            box-shadow: inset 0 0 10px rgba(255, 0, 255, 0.3);
            text-align: center;
            font-size: 1.2em;
            margin-bottom: 30px;
            position: relative;
        }
        .header-bar::before {
            content: " [ SYSTEM ACTIVE ] ";
            position: absolute;
            top: -10px;
            left: 20px;
            background: var(--dark-bg);
            color: var(--neon-magenta);
            font-size: 0.8em;
            padding: 0 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 1;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.15);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.4);
            border-color: var(--neon-cyan);
            transform: scale(1.01);
        }
        .panel h2 {
            color: var(--neon-magenta);
            text-shadow: 0 0 8px var(--neon-magenta);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 10px;
            font-size: 1.3em;
            margin-top: 0;
        }
        .panel.assault { border-color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 51, 51, 0.15); }
        .panel.assault h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); border-bottom-color: var(--neon-red); }
        .panel.assault:hover { box-shadow: 0 0 25px rgba(255, 51, 51, 0.4); border-color: var(--neon-red); }

        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        .status-bg {
            color: var(--neon-cyan);
            text-shadow: 0 0 8px var(--neon-cyan);
            font-size: 0.9em;
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 8px 4px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: var(--neon-cyan); font-size: 0.85em; opacity: 0.8; }
        
        .radar-box {
            height: 120px;
            background: rgba(0, 255, 0, 0.05);
            border: 1px solid var(--neon-green);
            margin-top: 15px;
            position: relative;
            overflow: hidden;
            font-size: 0.8em;
            padding: 10px;
            color: var(--neon-green);
            box-shadow: inset 0 0 15px rgba(0,255,0,0.2);
        }
        .radar-box::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(180deg, transparent 50%, rgba(0, 255, 0, 0.2) 100%);
            animation: scan 3s linear infinite;
        }

        .metric-row { display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding: 10px 0; align-items: center;}
        .metric-val { font-weight: bold; text-shadow: 0 0 5px currentColor; }
        
        .blinking-cursor::after { content: '_'; animation: blink 1s step-start infinite; }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }
        @keyframes blink { 50% { opacity: 0; } }
        @keyframes scan { 0% { transform: translateY(-100%); } 100% { transform: translateY(100%); } }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan); }
            20%, 24%, 55% { text-shadow: none; }
        }
    </style>
</head>
<body class="crt">
    <h1>🛰️ ORBITAL COMMAND <span style="font-size: 0.5em; color: var(--neon-magenta)">v3.0</span></h1>
    
    <div class="header-bar">
        <span class="status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span> | UPLINK: <span style="color:var(--neon-cyan)">SECURE</span>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel assault">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr>
                    <th>UNITA'</th>
                    <th>TARGET</th>
                    <th>STRATEGIA</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td><strong>SQUADRA_ALPHA</strong> 🐺</td>
                    <td>Binance</td>
                    <td>Scalper L1</td>
                    <td class="status-online">[ ACTIVE ]</td>
                </tr>
                <tr>
                    <td><strong>SQUADRA_DELTA</strong> 🦅</td>
                    <td>Cross-Exch</td>
                    <td>Order Flow</td>
                    <td class="status-online">[ ACTIVE ]</td>
                </tr>
                <tr>
                    <td><strong>SQUADRA_GAMMA</strong> 🐍</td>
                    <td>Bitget</td>
                    <td>Pairs Trading</td>
                    <td class="status-online">[ ACTIVE ]</td>
                </tr>
            </table>
            <div class="radar-box" id="hft-log">
                > INITIALIZING TACTICAL OVERVIEW...<br>
                > ALPHA: ENGAGED ON BTC/USDT.<br>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>⚕️ PROTOCOLLO TRINITY</h2>
            <table>
                <tr>
                    <th>NOME IN CODICE</th>
                    <th>OPERAZIONE</th>
                    <th>NETWORK</th>
                    <th>STATUS</th>
                </tr>
                <tr>
                    <td><strong>LO STROZZINO</strong> 🏦</td>
                    <td>Funding Arb</td>
                    <td>CEX/DEX</td>
                    <td class="status-bg">ONLINE BG ⚡</td>
                </tr>
                <tr>
                    <td><strong>IL CONTABILE</strong> 🧮</td>
                    <td>Smart DCA</td>
                    <td>Binance</td>
                    <td class="status-bg">ONLINE BG ⚡</td>
                </tr>
                <tr>
                    <td><strong>L'ANGELO CUSTODE</strong> 👼</td>
                    <td>MEV Protect</td>
                    <td>Arbitrum</td>
                    <td class="status-bg">ONLINE BG ⚡</td>
                </tr>
            </table>
            <div class="radar-box" style="border-color: var(--neon-cyan); color: var(--neon-cyan); background: rgba(0, 255, 255, 0.05); box-shadow: inset 0 0 15px rgba(0,255,255,0.2);">
                > TRINITY BACKGROUND DAEMONS RUNNING.<br>
                > MEV SHIELD: DEPLOYED.<br>
                > DCA ALGORITHM: ACCUMULATING.<br>
                <span class="blinking-cursor">> SYSTEM STABLE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-green); border-bottom-color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green);">📊 METRICHE DI MERCATO</h2>
            <div class="metric-row">
                <span>👁️ THE ORACLE <small>(Binance Sent.)</small></span>
                <span class="metric-val" style="color:var(--neon-magenta)">BULLISH [78%] 📈</span>
            </div>
            <div class="metric-row">
                <span>🐳 WHALE TRACKER <small>(Flows)</small></span>
                <span class="metric-val" style="color:var(--neon-cyan)">INFLOW +$42.5M 🌊</span>
            </div>
            <div class="metric-row">
                <span>⚠️ VOLATILITY INDEX</span>
                <span class="metric-val" style="color:var(--neon-red); animation: pulse 1s infinite;">ELEVATED (4.2σ)</span>
            </div>
            <div class="metric-row">
                <span>⚡ SYS. LATENCY</span>
                <span class="metric-val" style="color:var(--neon-green)">12ms ✅</span>
            </div>
            <div class="metric-row">
                <span>💧 GLOBAL LIQUIDITY</span>
                <span class="metric-val" style="color:var(--neon-green)">OPTIMAL</span>
            </div>
        </div>
    </div>

    <script>
        const hftLog = document.getElementById('hft-log');
        const lines = [
            "> DELTA: ORDER BOOK IMBALANCE DETECTED.",
            "> GAMMA: EXECUTING SPREAD ARBITRAGE.",
            "> ALPHA: LIMIT ORDER FILLED @ 68,450.",
            "> ALPHA: RECALIBRATING TWAP...",
            "> SYSTEM: SUB-MILLISECOND LATENCY CONFIRMED."
        ];
        setInterval(() => {
            const p = document.createElement('div');
            p.innerText = lines[Math.floor(Math.random() * lines.length)];
            hftLog.appendChild(p);
            if(hftLog.children.length > 5) hftLog.removeChild(hftLog.firstChild);
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run silently on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
