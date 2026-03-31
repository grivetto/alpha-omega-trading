from flask import Flask, render_template_string
import os

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
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
            --border-color: #39ff14;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            margin-top: 0;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 4s infinite;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 15px;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.2), 0 0 10px rgba(57, 255, 20, 0.1);
            position: relative;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 10px; height: 10px;
            border-top: 2px solid var(--neon-green);
            border-left: 2px solid var(--neon-green);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-green);
            border-right: 2px solid var(--neon-green);
        }

        .status-online {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            animation: pulse 2s infinite;
        }

        .status-active {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            animation: blink 1s infinite;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }

        .data-table th, .data-table td {
            border: 1px solid rgba(57, 255, 20, 0.3);
            padding: 8px;
            text-align: left;
            font-size: 0.9em;
        }

        .data-table th {
            color: var(--neon-blue);
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green); opacity: 1; }
            20%, 22%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(57,255,20,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }

        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1>🛰️ NUVOLA :: ORBITAL COMMAND</h1>
        <p>SYSTEM STATUS: <span class="status-online">ONLINE</span> | UPLINK: SECURE | TRINITY PROTOCOL: ENGAGED</p>
        <h3 style="color: var(--neon-pink); font-weight: bold; margin-top: 10px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p><strong>[+] SQUADRA_ALPHA</strong> 🦅 <br>
               Target: Binance Scalper <br>
               Status: <span class="status-active">ENGAGED</span> | Latency: 12ms</p>
            <p><strong>[+] SQUADRA_DELTA</strong> 🌪️ <br>
               Target: Order Flow Analysis <br>
               Status: <span class="status-online">MONITORING</span> | Book Imbalance: +4.2%</p>
            <p><strong>[+] SQUADRA_GAMMA</strong> ⚖️ <br>
               Target: Bitget Pairs Trading <br>
               Status: <span class="status-active">ARBITRAGING</span> | Spread: 0.15%</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-blue);">🛡️ PROTOCOLLO TRINITY</h2>
            <table class="data-table">
                <tr>
                    <th>Agente</th>
                    <th>Ruolo</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>🕴️ Lo Strozzino</td>
                    <td>Funding Arb</td>
                    <td><span class="status-online">YIELDING (APR 18%)</span></td>
                </tr>
                <tr>
                    <td>🧮 Il Contabile</td>
                    <td>DCA Accumulation</td>
                    <td><span class="status-online">ACCUMULATING</span></td>
                </tr>
                <tr>
                    <td>👼 L'Angelo Custode</td>
                    <td>MEV Arbitrum</td>
                    <td><span class="status-online">GUARDING (0 Tx)</span></td>
                </tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p>👁️ <strong>The Oracle (Binance Sentiment):</strong></p>
            <div style="width: 100%; background: #222; height: 15px; margin-bottom: 10px;">
                <div style="width: 78%; background: var(--neon-green); height: 100%; text-align: right; padding-right: 5px; font-size: 0.8em; color: black; font-weight: bold;">BULLISH 78%</div>
            </div>
            <p>🐋 <strong>Whale Tracker:</strong></p>
            <table class="data-table" style="color: var(--neon-pink);">
                <tr>
                    <th>Tx Hash</th>
                    <th>Size</th>
                    <th>Action</th>
                </tr>
                <tr>
                    <td>0x8f3...a1b</td>
                    <td>450 BTC</td>
                    <td>EXCHANGE INFLOW</td>
                </tr>
                <tr>
                    <td>0x1a2...c9d</td>
                    <td>12,000 ETH</td>
                    <td>DEX SWAP</td>
                </tr>
            </table>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; font-size: 0.8em; opacity: 0.7;">
        [TERMINAL READY] _
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
