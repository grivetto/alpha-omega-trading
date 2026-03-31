from flask import Flask, render_template_string
import threading
import time

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
            --bg-color: #0a0a0c;
            --neon-green: #00ff41;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --panel-bg: rgba(16, 20, 24, 0.85);
            --border-color: #1a2b3c;
        }

        @font-face {
            font-family: 'Share Tech Mono';
            src: url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace, Consolas;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 65, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 65, 0.03) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            margin-top: 0;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: 0 5px 15px rgba(0, 243, 255, 0.2);
            text-shadow: 0 0 10px var(--neon-blue);
            color: var(--neon-blue);
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 20px;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 10px rgba(0, 255, 65, 0.1);
            transition: all 0.3s ease;
        }

        .panel:hover {
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 15px var(--neon-green);
            border-color: var(--neon-green);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            opacity: 0.5;
        }

        .panel-blue:hover {
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 15px var(--neon-blue);
            border-color: var(--neon-blue);
        }
        
        .panel-blue::before {
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
        }

        .panel-purple:hover {
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 15px var(--neon-purple);
            border-color: var(--neon-purple);
        }
        
        .panel-purple::before {
            background: linear-gradient(90deg, transparent, var(--neon-purple), transparent);
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
            box-shadow: 0 0 8px currentColor;
        }

        .status-online { background-color: var(--neon-green); color: var(--neon-green); animation: pulse 2s infinite; }
        .status-offline { background-color: var(--neon-red); color: var(--neon-red); }
        .status-standby { background-color: #ffb700; color: #ffb700; }

        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 8px currentColor; }
            50% { opacity: 0.4; box-shadow: 0 0 2px currentColor; }
            100% { opacity: 1; box-shadow: 0 0 8px currentColor; }
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin-bottom: 12px;
            padding: 8px;
            background: rgba(0,0,0,0.4);
            border-left: 3px solid var(--neon-green);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .blue-list li { border-left-color: var(--neon-blue); color: var(--neon-blue); }
        .purple-list li { border-left-color: var(--neon-purple); color: var(--neon-purple); }

        .metric-value {
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,65,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }

        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9em;
        }

        th, td {
            border: 1px solid rgba(0, 255, 65, 0.2);
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: rgba(0, 255, 65, 0.1);
            color: var(--neon-green);
        }

        .glitch {
            position: relative;
            color: white;
            font-size: 2em;
            letter-spacing: 5px;
            animation: glitch-skew 1s infinite linear alternate-reverse;
        }
        
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1 class="glitch">🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>NUVOLA TACTICAL QUANTITATIVE DASHBOARD // SYSTEM: ONLINE</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-blue); background: rgba(0, 243, 255, 0.1); color: var(--neon-blue); font-weight: bold; font-size: 1.2em; display: inline-block; box-shadow: 0 0 10px rgba(0, 243, 255, 0.3); border-radius: 4px;">
            <span class="status-indicator status-online" style="box-shadow: 0 0 8px var(--neon-blue); background-color: var(--neon-blue);"></span> ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span><span class="status-indicator status-online"></span> <b>SQUADRA_ALPHA</b> <br><small>⚡ Scalper su Binance</small></span>
                    <span class="metric-value">+4.2%</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online"></span> <b>SQUADRA_DELTA</b> <br><small>🌊 Order Flow</small></span>
                    <span class="metric-value">+1.8%</span>
                </li>
                <li>
                    <span><span class="status-indicator status-standby"></span> <b>SQUADRA_GAMMA</b> <br><small>⚖️ Pairs Trading (Bitget)</small></span>
                    <span class="metric-value" style="color:#ffb700;">AWAITING</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-blue">
            <h2 style="color: var(--neon-blue);">🛡️ PROTOCOLLO TRINITY</h2>
            <ul class="blue-list">
                <li>
                    <span><span class="status-indicator status-online"></span> <b>Lo Strozzino</b> <br><small>💸 Funding Arb (Perp/Spot)</small></span>
                    <span class="metric-value">ACTIVE</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online"></span> <b>Il Contabile</b> <br><small>📈 Smart DCA Engine</small></span>
                    <span class="metric-value">ACTIVE</span>
                </li>
                <li>
                    <span><span class="status-indicator status-online"></span> <b>L'Angelo Custode</b> <br><small>👼 MEV Protection (Arbitrum)</small></span>
                    <span class="metric-value">GUARDING</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-purple">
            <h2 style="color: var(--neon-purple);">👁️ METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 15px;">
                <strong>🔮 THE ORACLE (Binance Sentiment)</strong>
                <div style="width: 100%; background: #111; height: 10px; margin-top: 5px; border: 1px solid #333;">
                    <div style="width: 78%; background: var(--neon-purple); height: 100%; box-shadow: 0 0 10px var(--neon-purple);"></div>
                </div>
                <small style="color: #ccc;">BULLISH BIAS [78%]</small>
            </div>

            <strong>🐋 WHALE TRACKER (Last 15m)</strong>
            <table>
                <tr>
                    <th>ASSET</th>
                    <th>FLOW</th>
                    <th>SIZE</th>
                </tr>
                <tr>
                    <td>BTC/USDT</td>
                    <td style="color: var(--neon-green);">INFLOW</td>
                    <td>$45.2M</td>
                </tr>
                <tr>
                    <td>ETH/USDT</td>
                    <td style="color: var(--neon-red);">OUTFLOW</td>
                    <td>$12.8M</td>
                </tr>
                <tr>
                    <td>SOL/USDT</td>
                    <td style="color: var(--neon-green);">INFLOW</td>
                    <td>$8.4M</td>
                </tr>
            </table>
        </div>

    </div>

    <div style="text-align: center; margin-top: 40px; color: #555; font-size: 0.8em;">
        [TERMINAL UPLINK ESTABLISHED] // [LATENCY: 12ms] // [ENCRYPTION: AES-256-GCM]
    </div>

    <script>
        // Fake dynamic updates for realism
        setInterval(() => {
            const values = document.querySelectorAll('.metric-value');
            if(Math.random() > 0.7) {
                let val = parseFloat(values[0].innerText);
                values[0].innerText = '+' + (val + (Math.random() * 0.1 - 0.02)).toFixed(2) + '%';
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
    app.run(host='0.0.0.0', port=8080)
