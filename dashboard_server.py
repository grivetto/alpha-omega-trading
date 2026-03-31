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
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --bg-dark: #0a0a0f;
            --panel-bg: rgba(10, 10, 15, 0.85);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        body {
            background-color: var(--bg-dark);
            color: #ffffff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid var(--neon-blue);
            box-shadow: var(--border-glow);
            margin-bottom: 30px;
            background: linear-gradient(90deg, transparent, rgba(0, 243, 255, 0.1), transparent);
            text-shadow: 0 0 10px var(--neon-blue);
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
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2), 0 0 10px rgba(0, 0, 0, 0.5);
            padding: 20px;
            border-radius: 5px;
            position: relative;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 10px; height: 10px;
            border-top: 2px solid var(--neon-pink);
            border-left: 2px solid var(--neon-pink);
        }
        
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0;
            width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-pink);
            border-right: 2px solid var(--neon-pink);
        }

        .panel h2 {
            color: var(--neon-pink);
            border-bottom: 1px solid var(--neon-pink);
            padding-bottom: 10px;
            margin-top: 0;
            text-shadow: 0 0 5px var(--neon-pink);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.2);
        }

        .status-item:last-child {
            border-bottom: none;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 10px;
        }

        .online {
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: pulse 1.5s infinite;
        }

        .standby {
            background-color: #ffd700;
            box-shadow: 0 0 8px #ffd700;
        }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
            100% { opacity: 1; transform: scale(1); }
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 243, 255, 0.1);
            border: 1px solid rgba(0, 243, 255, 0.3);
            padding: 15px;
            text-align: center;
            border-radius: 3px;
        }

        .metric-value {
            font-size: 1.5em;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 5px;
            font-weight: bold;
        }

        .blink {
            animation: blinker 2s linear infinite;
        }

        @keyframes blinker {
            50% { opacity: 0; }
        }

        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-dark);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--neon-blue);
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p class="blink">SYSTEM ONLINE // UPLINK SECURE // NUVOLA NETWORK V3.0</p>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span><span class="status-dot online"></span> SQUADRA_ALPHA (Binance Scalper)</span>
                <span style="color: var(--neon-green)">ENGAGED</span>
            </div>
            <div class="status-item">
                <span><span class="status-dot online"></span> SQUADRA_DELTA (Order Flow)</span>
                <span style="color: var(--neon-green)">ENGAGED</span>
            </div>
            <div class="status-item">
                <span><span class="status-dot standby"></span> SQUADRA_GAMMA (Bitget Pairs)</span>
                <span style="color: #ffd700">STANDBY</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="background: rgba(57, 255, 20, 0.1); border: 1px solid var(--neon-green); padding: 10px; text-align: center; margin-bottom: 15px; color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status-item">
                <span><span class="status-dot online"></span> Lo Strozzino (Funding Arb)</span>
                <span style="color: var(--neon-green)">ACTIVE</span>
            </div>
            <div class="status-item">
                <span><span class="status-dot online"></span> Il Contabile (DCA Matrix)</span>
                <span style="color: var(--neon-green)">ACTIVE</span>
            </div>
            <div class="status-item">
                <span><span class="status-dot online"></span> L'Angelo Custode (Arbitrum MEV)</span>
                <span style="color: var(--neon-green)">ACTIVE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>Whale Tracker (Inflows)</div>
                    <div class="metric-value">+42.5M USDT</div>
                </div>
                <div class="metric-box">
                    <div>Nuvola PNL (24h)</div>
                    <div class="metric-value" style="color: var(--neon-green)">+$1,204.50</div>
                </div>
                <div class="metric-box">
                    <div>System Load</div>
                    <div class="metric-value" style="color: var(--neon-blue)">14.2%</div>
                </div>
            </div>
        </div>

    </div>

    <div style="text-align: center; margin-top: 40px; color: rgba(255,255,255,0.3); font-size: 0.8em;">
        [TERMINAL ACCESS GRANTED - SERGIO OP-CLEARANCE LEVEL 5]
    </div>

</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
