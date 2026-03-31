from flask import Flask, render_template_string
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.1));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2);
            padding: 15px;
            border-radius: 5px;
        }
        .panel.blue {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
        }
        .panel.blue h2 { text-shadow: 0 0 5px var(--neon-blue); }
        .panel.pink {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.2);
        }
        .panel.pink h2 { text-shadow: 0 0 5px var(--neon-pink); }
        
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1s infinite;
        }
        .item {
            margin: 10px 0;
            padding: 5px;
            border-left: 2px solid;
            background: rgba(0, 255, 0, 0.02);
        }
        .item-green { border-left-color: var(--neon-green); }
        .item-blue { border-left-color: var(--neon-blue); background: rgba(0, 255, 255, 0.02); }
        .item-pink { border-left-color: var(--neon-pink); background: rgba(255, 0, 255, 0.02); }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #333; padding: 8px; text-align: left; }
        th { color: var(--neon-pink); border-bottom: 1px solid var(--neon-pink); }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    <div class="header">
        <h1><span class="status"></span> ORBITAL COMMAND - NUVOLA NODE</h1>
        <p>UPLINK ESTABLISHED. SECURE CONNECTION ACTIVE. 🛰️</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item item-green">
                <strong>[ALPHA]</strong> Binance Scalper ⚡
                <br><small>Status: ENGAGED | Ping: 12ms | PNL: +1.24%</small>
            </div>
            <div class="item item-green">
                <strong>[DELTA]</strong> Order Flow Analyst 🌊
                <br><small>Status: MONITORING | Target: Liquidity Voids</small>
            </div>
            <div class="item item-green">
                <strong>[GAMMA]</strong> Bitget Pairs Trading ⚖️
                <br><small>Status: REBALANCING | Exposure: Delta-Neutral</small>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel blue">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div style="background-color: var(--neon-blue); color: var(--bg-color); padding: 5px; font-weight: bold; text-align: center; margin-bottom: 10px; border-radius: 3px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="item item-blue">
                <strong>🕴️ Lo Strozzino</strong> (Funding Arb)
                <br><small>Status: ONLINE | Spread: 0.045% | Position: Hedged</small>
            </div>
            <div class="item item-blue">
                <strong>🧮 Il Contabile</strong> (DCA Core)
                <br><small>Status: ONLINE | Next Buy: 14h 22m | Allocation: 100%</small>
            </div>
            <div class="item item-blue">
                <strong>🛡️ L'Angelo Custode</strong> (MEV Arbitrum)
                <br><small>Status: ONLINE | Mempool: Scanning | Gas: 0.12 gwei</small>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel pink">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>Module</th>
                    <th>Data Source</th>
                    <th>Signal Status</th>
                </tr>
                <tr>
                    <td>The Oracle 🧿</td>
                    <td>Binance Sentiment</td>
                    <td style="color: var(--neon-green);">BULLISH 🟢</td>
                </tr>
                <tr>
                    <td>Whale Tracker 🐋</td>
                    <td>Large Tx Detect</td>
                    <td style="color: yellow;">ACTIVE 🟡</td>
                </tr>
                <tr>
                    <td>Volatility IDX 📈</td>
                    <td>ATR 1H</td>
                    <td style="color: red;">ELEVATED 🔴</td>
                </tr>
            </table>
            <br>
            <div style="font-size: 0.8em; opacity: 0.7;">
                >> REAL-TIME FEED OVERRIDE...<br>
                >> PROCESSING QUANTITATIVE DATA...<br>
                >> READY.
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
