import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: #0a0a0a;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2 {
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            color: var(--neon-blue);
            margin-bottom: 30px;
            letter-spacing: 2px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2), inset 0 0 10px rgba(57, 255, 20, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateY(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateY(10000%); opacity: 0; }
        }
        .panel h3 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            margin-top: 0;
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 1.5s infinite; }
        .status-standby { color: #f0f000; text-shadow: 0 0 5px #f0f000; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; border-left: 2px solid var(--neon-blue); padding-left: 10px; }
        .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .metric-box { background: rgba(0, 243, 255, 0.1); padding: 10px; text-align: center; border: 1px solid var(--neon-blue); }
        .metric-value { font-size: 1.5em; font-weight: bold; color: white; text-shadow: 0 0 5px white; margin-top: 5px; }
        .glitch { animation: glitch 1s linear infinite; }
        @keyframes glitch { 
            2%, 64% { transform: translate(2px,0) skew(0deg); } 
            4%, 60% { transform: translate(-2px,0) skew(0deg); } 
            62% { transform: translate(0,0) skew(5deg); } 
        }
    </style>
</head>
<body>
    <h1 class="glitch">🛰️ ORBITAL COMMAND 🛰️</h1>
    <h2>SYSTEM STATUS: <span class="status-online">NOMINAL</span></h2>
    <h3 style="text-align: center; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            <ul>
                <li>
                    <strong>[SQUADRA_ALPHA]</strong> - 🟢 <span class="status-online">ENGAGED</span><br>
                    <small>Target: Binance Scalping | Latency: 12ms</small>
                </li>
                <li>
                    <strong>[SQUADRA_DELTA]</strong> - 🟡 <span class="status-standby">STANDBY</span><br>
                    <small>Target: Order Flow Analysis | Awaiting Imbalance</small>
                </li>
                <li>
                    <strong>[SQUADRA_GAMMA]</strong> - 🟢 <span class="status-online">ENGAGED</span><br>
                    <small>Target: Bitget Pairs Trading | Spread: 0.15%</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h3>🔺 PROTOCOLLO TRINITY</h3>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)<br>
                    Status: <span class="status-online">BACKGROUND ACTIVE</span>
                </li>
                <li>
                    <strong>💼 Il Contabile</strong> (Smart DCA)<br>
                    Status: <span class="status-online">ACCUMULATING</span>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Status: <span class="status-online">MONITORING MEMPOOL</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h3>📊 METRICHE DI MERCATO</h3>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>👁️ The Oracle (Sentiment)</div>
                    <div class="metric-value" style="color:var(--neon-green)">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>🐋 Whale Tracker</div>
                    <div class="metric-value" style="color:var(--neon-pink)">DETECTED 🚨</div>
                </div>
                <div class="metric-box">
                    <div>⚡ Global Volume (24h)</div>
                    <div class="metric-value">$42.5B</div>
                </div>
                <div class="metric-box">
                    <div>🛡️ Network Risk</div>
                    <div class="metric-value" style="color:var(--neon-blue)">LOW</div>
                </div>
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
