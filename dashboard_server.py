from flask import Flask, render_template_string
import random
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🛸</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --dark-bg: #0a0a0f;
            --panel-bg: rgba(10, 10, 15, 0.8);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--neon-blue);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            animation: pulse 2s infinite;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 8px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: var(--neon-pink);
            animation: scanline 4s linear infinite;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold;}
        .status-offline { color: red; text-shadow: 0 0 5px red; }
        .metric-value {
            font-size: 1.2em;
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            font-weight: bold;
        }
        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue); }
            100% { text-shadow: 0 0 10px var(--neon-blue); }
        }
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid rgba(0,243,255,0.3); padding: 10px; text-align: left; }
        th { color: var(--neon-pink); }
        tr:hover { background: rgba(0, 243, 255, 0.1); }
        
        .sub-text {
            color: #888;
            font-size: 0.9em;
            display: block;
            margin-top: 4px;
        }
        .unit-block {
            border-left: 3px solid var(--neon-blue);
            padding-left: 10px;
            margin-bottom: 15px;
            background: rgba(0, 243, 255, 0.05);
            padding: 10px;
        }
        .unit-block:hover { border-left-color: var(--neon-pink); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛸 Nuvola Orbital Command 🛸</h1>
        <p>SYSTEM STATUS: <span class="status-online blink">ONLINE</span> | UPTIME: 99.9% | ENCRYPTION: AES-256</p>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: #ff00ea;">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="unit-block">
                <strong>🐺 SQUADRA_ALPHA</strong> [Binance Scalper]
                <span style="float: right;" class="status-online">ACTIVE</span>
                <span class="sub-text">Latency: 12ms | Executions/sec: 45 | PnL: <span style="color: var(--neon-green)">+4.2%</span></span>
            </div>
            <div class="unit-block">
                <strong>🎯 SQUADRA_DELTA</strong> [Order Flow]
                <span style="float: right;" class="status-online">ACTIVE</span>
                <span class="sub-text">Tracking institutional blocks... Signals detected: 14</span>
            </div>
            <div class="unit-block">
                <strong>⚖️ SQUADRA_GAMMA</strong> [Bitget Pairs]
                <span style="float: right;" class="status-online">ACTIVE</span>
                <span class="sub-text">Spread correlation: 0.98 | Position: Hedged ✅</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; padding: 10px; background: rgba(0, 243, 255, 0.1); border: 1px solid var(--neon-blue); border-radius: 4px; text-align: center; font-weight: bold; text-shadow: 0 0 5px var(--neon-blue);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="unit-block">
                <strong>🦇 Lo Strozzino</strong> [Funding Arb]
                <span style="float: right;" class="status-online">BACKGROUND</span>
                <span class="sub-text">Yielding 18.4% APY across 4 exchanges. Capital: Deployed.</span>
            </div>
            <div class="unit-block">
                <strong>🧮 Il Contabile</strong> [DCA]
                <span style="float: right;" class="status-online">BACKGROUND</span>
                <span class="sub-text">Accumulation phase active (BTC, ETH, SOL). Next buy: 2h 14m.</span>
            </div>
            <div class="unit-block">
                <strong>👼 L'Angelo Custode</strong> [MEV Arbitrum]
                <span style="float: right;" class="status-online">BACKGROUND</span>
                <span class="sub-text">Scanning mempool for sandwich opportunities... Flashbots RPC connected.</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: #39ff14;">📈 METRICHE DI MERCATO</h2>
            <table>
                <tr>
                    <th>Sensor Module</th>
                    <th>Status / Value</th>
                </tr>
                <tr>
                    <td>👁️ The Oracle (Binance Sentiment)</td>
                    <td class="metric-value">BULLISH (78%)</td>
                </tr>
                <tr>
                    <td>🐋 Whale Tracker</td>
                    <td class="status-online">DETECTED ($45M)</td>
                </tr>
                <tr>
                    <td>⚡ Volatility Index</td>
                    <td class="metric-value">ELEVATED</td>
                </tr>
                <tr>
                    <td>🔥 Gas Tracker (ETH)</td>
                    <td style="color: #fff;">14 Gwei</td>
                </tr>
            </table>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 40px; font-size: 0.85em; opacity: 0.6; font-family: monospace;">
        <p>GHOST PROTOCOL INITIATED. UNAUTHORIZED ACCESS WILL BE TERMINATED.</p>
        <p>[ NUVOLA QUANTITATIVE SYSTEMS V2.4.1 ]</p>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
