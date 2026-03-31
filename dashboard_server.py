import os
from flask import Flask, render_template_string

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
            --bg: #050510;
            --text: #0ff;
            --accent1: #f0f;
            --accent2: #39ff14;
            --panel: rgba(10, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(0deg, transparent 24%, rgba(0, 255, 255, 0.05) 25%, rgba(0, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 255, 0.05) 75%, rgba(0, 255, 255, 0.05) 76%, transparent 77%, transparent), 
                linear-gradient(90deg, transparent 24%, rgba(0, 255, 255, 0.05) 25%, rgba(0, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 255, 0.05) 75%, rgba(0, 255, 255, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--text);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--text);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: glitch 3s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel);
            border: 1px solid var(--text);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1) inset, 0 0 10px rgba(0, 255, 255, 0.3);
            border-radius: 4px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--accent1);
            box-shadow: 0 0 10px var(--accent1);
        }
        .panel:nth-child(2)::before { background: var(--accent2); box-shadow: 0 0 10px var(--accent2); }
        .panel:nth-child(3)::before { background: var(--text); box-shadow: 0 0 10px var(--text); }
        
        .status-online { color: var(--accent2); text-shadow: 0 0 5px var(--accent2); font-weight: bold; animation: pulse 2s infinite; }
        .status-standby { color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        ul { list-style-type: square; padding-left: 20px; margin-bottom: 0; }
        li { margin-bottom: 15px; }
        
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
        @keyframes glitch {
            0% { text-shadow: 2px 0 var(--accent1), -2px 0 var(--text); }
            50% { text-shadow: -2px 0 var(--accent1), 2px 0 var(--text); }
            100% { text-shadow: 2px 0 var(--accent1), -2px 0 var(--text); }
        }
        
        .metric-bar {
            height: 12px;
            background: #222;
            margin-top: 8px;
            border-radius: 2px;
            overflow: hidden;
            border: 1px solid #444;
        }
        .metric-fill {
            height: 100%;
            background: var(--text);
            box-shadow: 0 0 10px var(--text);
            animation: loading 4s infinite alternate ease-in-out;
        }
        .metric-fill.high { background: var(--accent2); box-shadow: 0 0 10px var(--accent2); animation-duration: 2s; }
        .metric-fill.med { background: var(--accent1); box-shadow: 0 0 10px var(--accent1); animation-duration: 3s; }
        
        @keyframes loading { 0% { width: 40%; } 100% { width: 95%; } }
        
        .terminal {
            font-size: 0.85em;
            color: #aaa;
            margin-top: 20px;
            border-top: 1px dashed #555;
            padding-top: 15px;
            font-family: monospace;
        }
        .blink { animation: pulse 1s infinite step-end; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌐 ORBITAL COMMAND 🌐</h1>
        <p>NUVOLA TACTICAL DASHBOARD // SYS_VER 10.4.2 // <span class="status-online">CONNECTION SECURE</span></p>
        <p style="font-size: 1.2em; border: 1px solid var(--accent2); padding: 5px; display: inline-block; box-shadow: 0 0 10px var(--accent2);">⚙️ PROTOCOLLO TRINITY: <span class="status-online">Online (DCA, Funding, MEV)</span></p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--accent1);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[SQUADRA_ALPHA]</strong> - Scalper (Binance)<br>
                    Status: <span class="status-online">ENGAGED 🟢</span><br>
                    <span style="font-size: 0.8em; color: #888;">Target: SOL/USDT | WinRate: 72.1%</span>
                </li>
                <li>
                    <strong>[SQUADRA_DELTA]</strong> - Order Flow<br>
                    Status: <span class="status-standby">STANDBY 🟡</span><br>
                    <span style="font-size: 0.8em; color: #888;">Awaiting liquidity sweeps...</span>
                </li>
                <li>
                    <strong>[SQUADRA_GAMMA]</strong> - Pairs Trading (Bitget)<br>
                    Status: <span class="status-online">ENGAGED 🟢</span><br>
                    <span style="font-size: 0.8em; color: #888;">Spread: BTC/ETH | Z-Score: +2.4</span>
                </li>
            </ul>
            <div class="terminal">
                > SQUADRA_ALPHA exec order 0x8a92f...<br>
                > SQUADRA_GAMMA balancing exposure...<span class="blink">_</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--accent2);">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>[Lo Strozzino]</strong> - Funding Arb<br>
                    Status: <span class="status-online">ACTIVE 🟢</span><br>
                    <span style="font-size: 0.8em; color: #888;">Harvesting delta-neutral yield (APR 24.5%)</span>
                </li>
                <li>
                    <strong>[Il Contabile]</strong> - DCA Engine<br>
                    Status: <span class="status-online">ACTIVE 🟢</span><br>
                    <span style="font-size: 0.8em; color: #888;">Accumulating BTC @ Support Levels</span>
                </li>
                <li>
                    <strong>[L'Angelo Custode]</strong> - MEV (Arbitrum)<br>
                    Status: <span class="status-online">HUNTING 🟢</span><br>
                    <span style="font-size: 0.8em; color: #888;">Scanning mempool for sandwich ops...</span>
                </li>
            </ul>
            <div class="terminal">
                > TRINITY protocol fully synchronized.<br>
                > Background daemons nominal.<span class="blink">_</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--text);">📊 METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 15px;">
                <strong>[The Oracle]</strong> Binance Sentiment
                <div class="metric-bar"><div class="metric-fill high" style="width: 82%;"></div></div>
                <span style="font-size: 0.8em; color: #888;">Bullish divergence detected across 4H timeframe.</span>
            </div>
            <div style="margin-bottom: 15px;">
                <strong>[Whale Tracker]</strong> On-Chain Flow
                <div class="metric-bar"><div class="metric-fill med" style="width: 55%;"></div></div>
                <span style="font-size: 0.8em; color: #888;">Moderate exchange outflows. Accumulation phase.</span>
            </div>
            <div>
                <strong>[System Load]</strong> Orbital Core
                <div class="metric-bar"><div class="metric-fill" style="width: 25%; animation: none;"></div></div>
                <span style="font-size: 0.8em; color: #888;">CPU: 18% | RAM: 6.2GB | Ping: 12ms</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on default flask port or 8080 depending on env
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
