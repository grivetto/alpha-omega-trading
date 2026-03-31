import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌐</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-x: hidden;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 4px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            width: 100%;
            max-width: 1200px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
            margin-top: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }
        .panel.blue { border-color: var(--neon-blue); color: var(--neon-blue); }
        .panel.blue::before { background: linear-gradient(90deg, transparent, var(--neon-blue), transparent); }
        .panel.pink { border-color: var(--neon-pink); color: var(--neon-pink); }
        .panel.pink::before { background: linear-gradient(90deg, transparent, var(--neon-pink), transparent); }
        
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 5px;
        }
        .online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        ul { list-style-type: none; padding: 0; }
        li { margin: 8px 0; display: flex; align-items: center; gap: 10px; }
        
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .metrics-table th, .metrics-table td {
            border: 1px solid rgba(255,255,255,0.1);
            padding: 8px;
            text-align: left;
        }
        .metrics-table th { color: var(--neon-blue); }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA DASHBOARD 🛰️</h1>
    
    <div style="background-color: rgba(255,0,255,0.2); border: 1px solid var(--neon-pink); color: var(--neon-pink); padding: 15px; font-weight: bold; font-size: 1.2em; text-align: center; border-radius: 5px; margin-top: 10px; width: 100%; max-width: 1200px; text-shadow: 0 0 5px var(--neon-pink); box-sizing: border-box;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span class="blink">🟢</span> <strong>SQUADRA_ALPHA</strong> (Scalper su Binance) - <span class="online">ACTIVE</span></li>
                <li><span class="blink">🟢</span> <strong>SQUADRA_DELTA</strong> (Order Flow) - <span class="online">ACTIVE</span></li>
                <li><span class="blink">🟢</span> <strong>SQUADRA_GAMMA</strong> (Pairs Trading su Bitget) - <span class="online">ACTIVE</span></li>
            </ul>
            <div class="status">
                <span>Target: Maximum Extraction</span>
                <span class="online">100% OPERATIONAL</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>💸 <strong>Lo Strozzino</strong> (Funding Arb) - <span class="online">BACKGROUND ONLINE</span></li>
                <li>🧮 <strong>Il Contabile</strong> (DCA) - <span class="online">BACKGROUND ONLINE</span></li>
                <li>🛡️ <strong>L'Angelo Custode</strong> (MEV Arbitrum) - <span class="online">BACKGROUND ONLINE</span></li>
            </ul>
            <div class="status">
                <span>Trinity Status: Synchronized</span>
                <span class="online">STABLE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Module</th>
                        <th>Status / Reading</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>👁️ The Oracle (Binance)</td>
                        <td>Sentiment: <span style="color:var(--neon-green)">BULLISH (87%)</span></td>
                    </tr>
                    <tr>
                        <td>🐋 Whale Tracker</td>
                        <td>Large Tx: <span style="color:var(--neon-pink)">DETECTED ($50M+)</span></td>
                    </tr>
                    <tr>
                        <td>⚡ Network Latency</td>
                        <td><span class="blink">12ms</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <div style="margin-top: 30px; font-size: 0.8em; opacity: 0.7;">
        [SYSTEM LOG]: Nuvola Core v4.2.0 initialized. All systems nominal. Awaiting command...
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
