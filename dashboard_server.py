import os
from flask import Flask, render_template_string

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
            --neon-cyan: #0ff;
            --neon-red: #ff073a;
            --bg-color: #020202;
            --panel-bg: rgba(0, 20, 0, 0.4);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1 {
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan);
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 3s infinite alternate;
            letter-spacing: 4px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.2), 0 0 10px rgba(57, 255, 20, 0.5);
            padding: 20px;
            border-radius: 8px;
            backdrop-filter: blur(5px);
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: pan 2s linear infinite;
        }
        .panel h2 {
            font-size: 1.3rem;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            text-shadow: 0 0 5px var(--neon-green);
            color: var(--neon-green);
            margin-top: 0;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-standby { color: #fdfd96; text-shadow: 0 0 8px #fdfd96; font-weight: bold; }
        .status-active { color: var(--neon-cyan); text-shadow: 0 0 8px var(--neon-cyan); font-weight: bold; }
        .status-warning { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; animation: blink 1s infinite; }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin: 15px 0; font-size: 1rem; border-left: 2px solid #333; padding-left: 10px; }
        small { display: block; margin-top: 5px; color: #888; font-size: 0.8rem; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan); }
            20%, 24%, 55% { opacity: 0.5; text-shadow: none; }
        }
        @keyframes pan { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
        
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9rem;
            margin-top: 20px;
        }
        .data-grid div { 
            border: 1px solid rgba(57, 255, 20, 0.3); 
            padding: 10px; 
            text-align: center; 
            background: rgba(0, 0, 0, 0.5);
            border-radius: 4px;
        }
        .scan-line {
            position: fixed; top: 0; left: 0; width: 100%; height: 3px;
            background-color: rgba(57, 255, 20, 0.4); box-shadow: 0 0 15px var(--neon-green);
            animation: scan 6s linear infinite; z-index: 9999; pointer-events: none;
        }
        @keyframes scan { 0% { top: -10px; } 100% { top: 100%; } }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.8rem;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <p style="text-align: center; margin-bottom: 10px; font-size: 1.2rem;">
        SYSTEM STATUS: <span class="status-online">OPTIMAL</span> &nbsp;|&nbsp; 
        UPLINK: <span class="status-online">SECURE</span> &nbsp;|&nbsp; 
        LATENCY: <span class="status-active">12ms</span>
    </p>
    <p style="text-align: center; margin-bottom: 40px; font-size: 1.2rem; color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); font-weight: bold;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </p>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    🐺 <strong>SQUADRA_ALPHA</strong> (Binance Scalper)<br>
                    <span class="status-online">[ ONLINE 🟢 ]</span>
                    <small>Win Rate: 68.4% | Trades/Hr: 124 | PnL: +$412.50</small>
                </li>
                <li>
                    🌊 <strong>SQUADRA_DELTA</strong> (Order Flow)<br>
                    <span class="status-standby">[ STANDBY 🟡 ]</span>
                    <small>Status: Waiting for liquidity sweeps... | Depth: Analyzed</small>
                </li>
                <li>
                    ⚖️ <strong>SQUADRA_GAMMA</strong> (Bitget Pairs)<br>
                    <span class="status-online">[ ONLINE 🟢 ]</span>
                    <small>Spread Z-Score: +2.14 | Exposure: Delta Neutral</small>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    🩸 <strong>Lo Strozzino</strong> (Funding Arb)<br>
                    <span class="status-active">[ ACTIVE ⚡ ]</span>
                    <small>Yield: +18.4% APY | Hedged: 100% | Perp/Spot Delta: 0.04%</small>
                </li>
                <li>
                    🧮 <strong>Il Contabile</strong> (DCA Accumulator)<br>
                    <span class="status-online">[ ACCUMULATING 📈 ]</span>
                    <small>Asset: BTC | Avg Entry: $62,450 | Next Buy: In 14h</small>
                </li>
                <li>
                    🦇 <strong>L'Angelo Custode</strong> (Arbitrum MEV)<br>
                    <span class="status-active">[ PATROLLING 🦇 ]</span>
                    <small>Blocks Checked: 1,432,109 | Flashloans Executed: 3</small>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    🔮 <strong>THE ORACLE (Sentiment):</strong><br>
                    <span class="status-online">GREED (78)</span>
                </li>
                <li>
                    🐳 <strong>WHALE TRACKER:</strong><br>
                    <span class="status-warning">⚠️ 5,200 BTC -> BINANCE (HOT WALLET)</span>
                </li>
            </ul>
            <div class="data-grid">
                <div>BTC/USDT<br><span class="status-online">68,432.10</span></div>
                <div>ETH/USDT<br><span class="status-warning">3,541.20</span></div>
                <div>VOLATILITY<br><span class="status-active">HIGH</span></div>
                <div>GLOBAL LIQ<br><span class="status-online">$2.42T</span></div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        NUVOLA KINETIC FRAMEWORK v4.2.0 | UNAUTHORIZED ACCESS STRICTLY PROHIBITED
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on standard local port for dashboard
    app.run(host='0.0.0.0', port=5000, debug=False)
