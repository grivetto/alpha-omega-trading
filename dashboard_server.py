import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA C2</title>
    <style>
        :root {
            --bg-color: #050a0f;
            --main-neon: #00ff41;
            --alert-neon: #ff003c;
            --info-neon: #00f0ff;
            --border-glow: 0 0 10px var(--main-neon), 0 0 20px var(--main-neon);
        }
        body {
            background-color: var(--bg-color);
            color: var(--main-neon);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--main-neon);
            margin-bottom: 10px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--main-neon);
            padding-bottom: 20px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 255, 65, 0.2);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            border: 1px solid var(--main-neon);
            padding: 15px;
            background: rgba(0, 20, 0, 0.4);
            box-shadow: var(--border-glow);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid rgba(0, 255, 65, 0.5);
            pointer-events: none;
            z-index: -1;
        }
        .status {
            font-weight: bold;
            display: inline-block;
            padding: 2px 5px;
            border-radius: 3px;
            animation: pulse 1.5s infinite;
        }
        .status.online { color: #fff; background-color: var(--main-neon); text-shadow: none; }
        .status.standby { color: #fff; background-color: var(--info-neon); text-shadow: none; }
        .status.alert { color: #fff; background-color: var(--alert-neon); text-shadow: none; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            color: var(--info-neon);
        }
        th, td {
            border: 1px solid var(--info-neon);
            padding: 8px;
            text-align: left;
            font-size: 0.9em;
        }
        th {
            background-color: rgba(0, 240, 255, 0.1);
        }
        
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,65,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 8s linear infinite;
        }
        @keyframes scanline {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        
        .sys-log {
            font-size: 0.8em;
            color: #888;
            margin-top: 5px;
            height: 60px;
            overflow: hidden;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
        <h3>[ CLASSIFIED TACTICAL C2 INTERFACE ]</h3>
        <p>SYSTEM STATUS: <span class="status online">OPERATIONAL</span> | UPLINK: <span style="color:var(--info-neon)">SECURE</span></p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <hr style="border-color: var(--main-neon);">
            <p><strong>[A] SQUADRA_ALPHA</strong> (Scalper su Binance)<br>
               STATUS: <span class="status online">ENGAGING</span> | ROI: +0.45% / hr<br>
               <span class="sys-log">> Executing micro-trades... Latency 14ms</span>
            </p>
            <p><strong>[D] SQUADRA_DELTA</strong> (Order Flow)<br>
               STATUS: <span class="status standby">MONITORING</span> | ORDER BOOK: IMBALANCED<br>
               <span class="sys-log">> Awaiting liquidity gaps...</span>
            </p>
            <p><strong>[G] SQUADRA_GAMMA</strong> (Pairs Trading su Bitget)<br>
               STATUS: <span class="status online">HEDGED</span> | SPREAD: 0.8%<br>
               <span class="sys-log">> Arbitrage locked on BTC/ETH pair...</span>
            </p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <hr style="border-color: var(--info-neon);">
            <p style="color: var(--main-neon); font-weight: bold; text-align: center; border: 1px dashed var(--main-neon); padding: 5px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <p><strong>🎩 Lo Strozzino</strong> (Funding Arb)<br>
               STATUS: <span class="status online">COLLECTING</span> | APY: 18.2%<br>
               <span class="sys-log">> Harvesting funding rates across perp markets...</span>
            </p>
            <p><strong>🧮 Il Contabile</strong> (DCA)<br>
               STATUS: <span class="status online">ACCUMULATING</span> | NEXT BUY: 4h 12m<br>
               <span class="sys-log">> DCA routing optimal. Fiat reserves nominal.</span>
            </p>
            <p><strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
               STATUS: <span class="status alert">HUNTING</span> | MEMPOOL: ACTIVE<br>
               <span class="sys-log">> Scanning mempool for frontrun targets...</span>
            </p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO (INTEL)</h2>
            <hr style="border-color: var(--alert-neon);">
            <table>
                <tr>
                    <th>SENSOR</th>
                    <th>TARGET</th>
                    <th>READING</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle</td>
                    <td>Binance Sentiment</td>
                    <td style="color: var(--main-neon);">BULLISH (72%)</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td>On-Chain Moves</td>
                    <td style="color: var(--alert-neon);">SEVERE OUTFLOW</td>
                </tr>
                <tr>
                    <td>🩸 Volatility Index</td>
                    <td>Global Market</td>
                    <td style="color: var(--info-neon);">ELEVATED</td>
                </tr>
                <tr>
                    <td>⛽ Gas Monitor</td>
                    <td>ETH Mainnet</td>
                    <td style="color: var(--main-neon);">15 Gwei</td>
                </tr>
            </table>
            <p class="sys-log" style="margin-top:15px; color: var(--info-neon);">> FEED LIVE. ENCRYPTED.</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    os.makedirs('/home/sergio/.openclaw/workspace/denaro', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)
