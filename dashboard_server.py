from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ NUVOLA ORBITAL COMMAND ⚡</title>
    <style>
        :root {
            --bg-color: #050510;
            --neon-blue: #0ff;
            --neon-purple: #b026ff;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --text-color: #e0e0e0;
            --panel-bg: rgba(10, 10, 25, 0.8);
            --border-color: rgba(0, 255, 255, 0.3);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            animation: pulse 2s infinite alternate;
        }
        @keyframes pulse {
            from { text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); }
            to { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px var(--neon-blue), 0 0 40px var(--neon-blue); }
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.1) inset;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3) inset, 0 0 10px var(--neon-blue);
            border-color: var(--neon-blue);
        }
        .panel h2 {
            margin-top: 0;
            border-bottom: 1px dashed var(--border-color);
            padding-bottom: 10px;
        }
        .neon-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .neon-purple { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        .neon-green { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .neon-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .online { background-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); animation: blink 1s infinite; }
        .offline { background-color: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .standby { background-color: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }
        
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .metric-value {
            font-weight: bold;
        }
        .progress-bar {
            width: 100%;
            height: 5px;
            background-color: #333;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background-color: var(--neon-blue);
            box-shadow: 0 0 5px var(--neon-blue);
        }
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-color);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            animation: glitch-anim-1 2s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        @keyframes glitch-anim-1 {
            0% { clip: rect(20px, 9999px, 15px, 0); }
            100% { clip: rect(100px, 9999px, 15px, 0); }
        }
        @keyframes glitch-anim-2 {
            0% { clip: rect(10px, 9999px, 85px, 0); }
            100% { clip: rect(50px, 9999px, 85px, 0); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch" data-text="🛰️ ORBITAL COMMAND TACTICAL DASHBOARD 🛰️">🛰️ ORBITAL COMMAND TACTICAL DASHBOARD 🛰️</h1>
        <p>SYSTEM STATUS: <span class="neon-green">OPTIMAL</span> | UPLINK: <span class="neon-blue">SECURE</span></p>
        <div style="margin-top: 10px; padding: 10px; border: 1px solid var(--neon-purple); background-color: rgba(176, 38, 255, 0.1); display: inline-block; border-radius: 5px; box-shadow: 0 0 15px rgba(176, 38, 255, 0.3);">
            <strong><span class="neon-purple">⚙️ PROTOCOLLO TRINITY:</span> <span class="neon-green">Online</span> (DCA, Funding, MEV)</strong>
        </div>
    </div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="neon-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="metric-row">
                <span><span class="status-dot online"></span>SQUADRA_ALPHA</span>
                <span class="metric-value neon-blue">Scalper su Binance</span>
            </div>
            <div class="metric-row">
                <span>Latency</span>
                <span class="metric-value">{{ alpha_latency }}ms</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 95%; background-color: var(--neon-red);"></div></div>
            <br>
            
            <div class="metric-row">
                <span><span class="status-dot online"></span>SQUADRA_DELTA</span>
                <span class="metric-value neon-purple">Order Flow</span>
            </div>
            <div class="metric-row">
                <span>Win Rate (1h)</span>
                <span class="metric-value">68.4%</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 68%; background-color: var(--neon-purple);"></div></div>
            <br>
            
            <div class="metric-row">
                <span><span class="status-dot standby"></span>SQUADRA_GAMMA</span>
                <span class="metric-value neon-green">Pairs Trading su Bitget</span>
            </div>
            <div class="metric-row">
                <span>Status</span>
                <span class="metric-value">Awaiting Divergence</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="neon-purple">💠 PROTOCOLLO TRINITY</h2>
            
            <div class="metric-row">
                <span><span class="status-dot online"></span>Lo Strozzino</span>
                <span class="metric-value neon-red">Funding Arb</span>
            </div>
            <div class="metric-row">
                <span>Current APR</span>
                <span class="metric-value">+14.2%</span>
            </div>
            <br>
            
            <div class="metric-row">
                <span><span class="status-dot online"></span>Il Contabile</span>
                <span class="metric-value neon-blue">DCA Engine</span>
            </div>
            <div class="metric-row">
                <span>Next Execution</span>
                <span class="metric-value">04:12:00</span>
            </div>
            <br>
            
            <div class="metric-row">
                <span><span class="status-dot online"></span>L'Angelo Custode</span>
                <span class="metric-value neon-green">MEV Arbitrum</span>
            </div>
            <div class="metric-row">
                <span>Blocks Scanned</span>
                <span class="metric-value">1,402,991</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="neon-green">📊 METRICHE DI MERCATO</h2>
            
            <div class="metric-row">
                <span class="neon-blue">👁️ THE ORACLE (Sentiment)</span>
                <span class="metric-value">{{ oracle_sentiment }}</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: {{ oracle_width }}%; background-color: {{ oracle_color }};"></div></div>
            <br>
            
            <div class="metric-row">
                <span class="neon-purple">🐋 WHALE TRACKER</span>
                <span class="metric-value">Large Inflows Detected</span>
            </div>
            <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">
                > TX: 0x8f4...2a1 | 1,200 BTC<br>
                > TX: 0x3a1...9b2 | 50,000 ETH
            </div>
            <br>
            
            <div class="metric-row">
                <span class="neon-red">🔥 VOLATILITY INDEX</span>
                <span class="metric-value">{{ volatility }}</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width: 85%; background-color: var(--neon-red);"></div></div>
        </div>
    </div>
    
    <div style="margin-top: 30px; text-align: center; font-size: 0.8em; color: #555;">
        > NUVOLA CORE v4.2.0 | UNAUTHORIZED ACCESS IS FATAL &lt;
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(
        HTML_TEMPLATE,
        alpha_latency=random.randint(5, 15),
        oracle_sentiment=random.choice(["BULLISH", "NEUTRAL", "BEARISH"]),
        oracle_width=random.randint(40, 90),
        oracle_color=random.choice(["#39ff14", "#ff073a", "#0ff"]),
        volatility=round(random.uniform(40.0, 80.0), 2)
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)