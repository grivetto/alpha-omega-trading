import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-dark: #0a0a0c;
            --panel-bg: rgba(15, 20, 25, 0.85);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 255, 255, 0.05) 0%, transparent 60%),
                linear-gradient(rgba(0, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 100% 100%, 30px 30px, 30px 30px;
            background-attachment: fixed;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        h1 {
            text-align: center;
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan);
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 40px;
            font-size: 2.5em;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.15), inset 0 0 20px rgba(0, 255, 255, 0.05);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-cyan);
            box-shadow: 0 0 15px var(--neon-cyan);
            animation: scanline 4s linear infinite;
            opacity: 0.7;
        }
        @keyframes scanline {
            0% { top: -10%; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: 110%; opacity: 0; }
        }
        .panel h2 {
            font-size: 1.4em;
            margin-bottom: 20px;
            text-shadow: 0 0 8px currentColor;
        }
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid var(--neon-green);
            border-radius: 0 4px 4px 0;
            transition: all 0.3s ease;
        }
        .status:hover {
            background: rgba(0, 255, 255, 0.1);
            transform: translateX(5px);
        }
        .badge {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            font-weight: bold;
            font-size: 1.1em;
            animation: pulse 2s infinite;
            padding: 5px 10px;
            border: 1px solid var(--neon-green);
            border-radius: 4px;
            background: rgba(57, 255, 20, 0.1);
        }
        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 5px currentColor; }
            50% { opacity: 0.6; box-shadow: 0 0 2px currentColor; }
            100% { opacity: 1; box-shadow: 0 0 5px currentColor; }
        }
        .metric-container {
            flex-direction: column;
            align-items: flex-start;
        }
        .metric-title {
            font-size: 1.1em;
            margin-bottom: 12px;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            width: 100%;
            margin: 6px 0;
            font-size: 0.95em;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 4px;
        }
        .metric-row span:last-child {
            color: #fff;
            font-weight: bold;
        }
        
        /* Panel specific colors */
        .panel-assault { border-color: var(--neon-cyan); }
        .panel-assault h2 { color: var(--neon-cyan); }
        .panel-assault .status { border-left-color: var(--neon-cyan); }
        .panel-assault .badge { color: var(--neon-cyan); border-color: var(--neon-cyan); background: rgba(0, 255, 255, 0.1); text-shadow: 0 0 8px var(--neon-cyan); }
        
        .panel-trinity { border-color: var(--neon-magenta); }
        .panel-trinity h2 { color: var(--neon-magenta); }
        .panel-trinity .status { border-left-color: var(--neon-magenta); }
        .panel-trinity .badge { color: var(--neon-magenta); border-color: var(--neon-magenta); background: rgba(255, 0, 255, 0.1); text-shadow: 0 0 8px var(--neon-magenta); }

        .panel-metrics { border-color: var(--neon-green); }
        .panel-metrics h2 { color: var(--neon-green); }
        .panel-metrics .status { border-left-color: var(--neon-green); }
        
        .footer {
            text-align: center;
            margin-top: 50px;
            font-size: 0.9em;
            opacity: 0.8;
            color: var(--neon-cyan);
            text-shadow: 0 0 4px var(--neon-cyan);
            animation: flicker 4s infinite;
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 0.8; }
            20%, 24%, 55% { opacity: 0.2; }
        }
    </style>
</head>
<body>
    <h1>🛰️ Nuvola :: Orbital Command</h1>
    
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.2em; color: var(--neon-magenta); text-shadow: 0 0 10px var(--neon-magenta); border: 1px solid var(--neon-magenta); padding: 10px; background: rgba(255, 0, 255, 0.1); border-radius: 8px; animation: pulse 2s infinite;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel panel-assault">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <div>
                    <strong>🐺 SQUADRA_ALPHA</strong><br>
                    <small style="color: #aaa;">Scalper Ultra-Fast // Binance</small>
                </div>
                <div class="badge">ENGAGED</div>
            </div>
            <div class="status">
                <div>
                    <strong>🌊 SQUADRA_DELTA</strong><br>
                    <small style="color: #aaa;">Order Flow Imbalance // Multi-CEX</small>
                </div>
                <div class="badge">ENGAGED</div>
            </div>
            <div class="status">
                <div>
                    <strong>⚖️ SQUADRA_GAMMA</strong><br>
                    <small style="color: #aaa;">Statistical Pairs Trading // Bitget</small>
                </div>
                <div class="badge">ENGAGED</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status">
                <div>
                    <strong>💼 Lo Strozzino</strong><br>
                    <small style="color: #aaa;">Funding Rate Arbitrage // Perpetual</small>
                </div>
                <div class="badge">ACTIVE</div>
            </div>
            <div class="status">
                <div>
                    <strong>🧮 Il Contabile</strong><br>
                    <small style="color: #aaa;">Smart DCA & Rebalancing Engine</small>
                </div>
                <div class="badge">ACTIVE</div>
            </div>
            <div class="status">
                <div>
                    <strong>🛡️ L'Angelo Custode</strong><br>
                    <small style="color: #aaa;">MEV Protection & Sniping // Arbitrum</small>
                </div>
                <div class="badge">ACTIVE</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-metrics">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="status metric-container">
                <div class="metric-title">👁️ THE ORACLE (Sentiment)</div>
                <div class="metric-row"><span>BTC L/S Ratio:</span> <span style="color: var(--neon-green);">1.45 (Bullish)</span></div>
                <div class="metric-row"><span>Fear & Greed Index:</span> <span style="color: var(--neon-green);">74 (Greed)</span></div>
                <div class="metric-row"><span>OB Imbalance (1m):</span> <span style="color: var(--neon-green);">+12.4% Bids</span></div>
                <div class="metric-row"><span>Binance Funding:</span> <span style="color: var(--neon-magenta);">0.015%</span></div>
            </div>
            <div class="status metric-container" style="margin-top: 20px;">
                <div class="metric-title">🐋 WHALE TRACKER</div>
                <div class="metric-row"><span>Large TXs (24h):</span> <span>1,432</span></div>
                <div class="metric-row"><span>Net CEX Inflow:</span> <span style="color: #ff3333;">-4,250 BTC</span></div>
                <div class="metric-row"><span>DEX Swaps >$1M:</span> <span>42</span></div>
                <div style="margin-top: 10px; padding: 8px; background: rgba(255,255,0,0.1); border: 1px solid yellow; color: yellow; font-size: 0.9em; width: calc(100% - 16px); text-align: center; border-radius: 4px; animation: pulse 1.5s infinite;">
                    ⚠️ ALERT: 2,500 BTC moved to Coinbase Prime
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        [ SYSTEM ONLINE ] :: [ ALL PROTOCOLS NOMINAL ] :: [ NUVOLA CORE v4.5.0-CYBER ] :: [ LATENCY: 12ms ]
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Usa port 5000 o quello che preferisci
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
