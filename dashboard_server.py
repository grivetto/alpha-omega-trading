import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        body {
            background-color: #0b0f19;
            color: #00ffcc;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 204, .05) 25%, rgba(0, 255, 204, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, .05) 75%, rgba(0, 255, 204, .05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 204, .05) 25%, rgba(0, 255, 204, .05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, .05) 75%, rgba(0, 255, 204, .05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        
        .crt::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        
        h1, h2, h3 {
            text-transform: uppercase;
            margin: 0;
            padding: 0;
        }
        
        h1 {
            text-align: center;
            font-size: 3.5em;
            margin-bottom: 5px;
            letter-spacing: 5px;
            color: #ff0055;
            text-shadow: 0 0 10px #ff0055, 0 0 20px #ff0055, 0 0 30px #ff0055;
            animation: glitch 2s infinite;
        }
        
        .subtitle {
            text-align: center;
            font-size: 1.2em;
            margin-bottom: 40px;
            color: #b3b3b3;
            text-shadow: 0 0 5px #fff;
            letter-spacing: 2px;
        }
        
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 30px;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .panel {
            background: rgba(0, 25px, 20, 0.7);
            border: 1px solid #00ffcc;
            border-radius: 8px;
            padding: 20px;
            box-shadow: inset 0 0 20px rgba(0, 255, 204, 0.2), 0 0 15px rgba(0, 255, 204, 0.3);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%; right: 0; height: 2px;
            width: 50%;
            background: linear-gradient(90deg, transparent, #00ffcc, transparent);
            animation: scanline 3s linear infinite;
        }
        
        .panel h2 {
            font-size: 1.3em;
            color: #00ffcc;
            text-shadow: 0 0 8px #00ffcc;
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(0, 255, 204, 0.3);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
        }
        
        .panel h2 span.icon {
            font-size: 1.5em;
            margin-right: 10px;
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 8px 10px;
            background: rgba(0, 255, 204, 0.05);
            border-left: 3px solid #00ffcc;
            transition: all 0.3s ease;
        }
        
        .metric-row:hover {
            background: rgba(0, 255, 204, 0.15);
            transform: translateX(5px);
            border-left: 3px solid #ff0055;
            box-shadow: 0 0 10px rgba(255, 0, 85, 0.4);
        }
        
        .status-online {
            color: #39ff14;
            text-shadow: 0 0 8px #39ff14;
            font-weight: bold;
            font-size: 0.9em;
            animation: pulse 1.5s infinite alternate;
        }
        
        .status-standby {
            color: #ffcc00;
            text-shadow: 0 0 8px #ffcc00;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .status-alert {
            color: #ff0055;
            text-shadow: 0 0 8px #ff0055;
            font-weight: bold;
            font-size: 0.9em;
            animation: flash 0.5s infinite alternate;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        
        @keyframes pulse {
            0% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        @keyframes flash {
            0% { opacity: 0.3; }
            100% { opacity: 1; text-shadow: 0 0 15px #ff0055; }
        }
        
        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 #00ffcc, -0.05em -0.025em 0 #ffcc00, 0.025em 0.05em 0 #ff0055; }
            14% { text-shadow: 0.05em 0 0 #00ffcc, -0.05em -0.025em 0 #ffcc00, 0.025em 0.05em 0 #ff0055; }
            15% { text-shadow: -0.05em -0.025em 0 #00ffcc, 0.025em 0.025em 0 #ffcc00, -0.05em -0.05em 0 #ff0055; }
            49% { text-shadow: -0.05em -0.025em 0 #00ffcc, 0.025em 0.025em 0 #ffcc00, -0.05em -0.05em 0 #ff0055; }
            50% { text-shadow: 0.025em 0.05em 0 #00ffcc, 0.05em 0 0 #ffcc00, 0 -0.05em 0 #ff0055; }
            99% { text-shadow: 0.025em 0.05em 0 #00ffcc, 0.05em 0 0 #ffcc00, 0 -0.05em 0 #ff0055; }
            100% { text-shadow: -0.025em 0 0 #00ffcc, -0.025em -0.025em 0 #ffcc00, -0.025em -0.05em 0 #ff0055; }
        }
        
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #555;
            font-size: 0.9em;
            letter-spacing: 1px;
        }
    </style>
</head>
<body class="crt">

    <h1>ORBITAL COMMAND</h1>
    <div class="subtitle">▶ ROOT ACCESS GRANTED // TACTICAL OVERVIEW ONLINE</div>
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.5em; font-weight: bold; color: #39ff14; text-shadow: 0 0 10px #39ff14; animation: pulse 1.5s infinite alternate; border: 2px dashed #39ff14; padding: 15px; display: inline-block; left: 50%; transform: translateX(-50%); position: relative; background: rgba(57, 255, 20, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2><span class="icon">⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric-row">
                <span>🐺 SQUADRA_ALPHA <br><small style="color:#aaa;">(Scalper Binance)</small></span>
                <span class="status-online">ENGAGED [28ms]</span>
            </div>
            <div class="metric-row">
                <span>⚡ SQUADRA_DELTA <br><small style="color:#aaa;">(Order Flow)</small></span>
                <span class="status-online">MONITORING</span>
            </div>
            <div class="metric-row">
                <span>⚖️ SQUADRA_GAMMA <br><small style="color:#aaa;">(Pairs Trading Bitget)</small></span>
                <span class="status-standby">AWAITING SIGNAL</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2><span class="icon">🛡️</span> PROTOCOLLO TRINITY</h2>
            <div class="metric-row">
                <span>💼 Lo Strozzino <br><small style="color:#aaa;">(Funding Arb)</small></span>
                <span class="status-online">ACTIVE [APR: 18.4%]</span>
            </div>
            <div class="metric-row">
                <span>🧮 Il Contabile <br><small style="color:#aaa;">(DCA)</small></span>
                <span class="status-online">ACTIVE [CYCLE: #42]</span>
            </div>
            <div class="metric-row">
                <span>👼 L'Angelo Custode <br><small style="color:#aaa;">(MEV Arbitrum)</small></span>
                <span class="status-online">PATROLLING IN BKG</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2><span class="icon">📡</span> METRICHE DI MERCATO</h2>
            <div class="metric-row">
                <span>👁️ The Oracle <br><small style="color:#aaa;">(Binance Sentiment)</small></span>
                <span class="status-alert">FEAR [34/100]</span>
            </div>
            <div class="metric-row">
                <span>🐋 Whale Tracker <br><small style="color:#aaa;">(On-Chain)</small></span>
                <span style="color:#00ffcc; text-align:right;">DETECTED:<br>1500 BTC ➡️ CEX</span>
            </div>
            <div class="metric-row">
                <span>🔥 Liquidity Heatmap <br><small style="color:#aaa;">(Orderbook)</small></span>
                <span style="color:#ffcc00;">DENSE @ $68,500</span>
            </div>
        </div>

    </div>

    <div class="footer">
        SYS.TIME: 2026-03-31 05:00 UTC // ALL SYSTEMS NOMINAL // NUVOLA OPERATIONAL
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Try to grab port 5000, or whatever is specified.
    app.run(host='0.0.0.0', port=5000)
