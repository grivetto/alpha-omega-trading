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
            --bg: #050505;
            --neon-green: #00ff00;
            --neon-cyan: #00ffff;
            --neon-magenta: #ff00ff;
            --neon-red: #ff0033;
            --neon-yellow: #ffff00;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            overflow-x: hidden;
        }
        /* Scanline effect */
        body::after {
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
            text-shadow: 0 0 10px var(--neon-cyan);
            color: var(--neon-cyan);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 30px;
            animation: flicker 4s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            z-index: 10;
            position: relative;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 12px rgba(0, 255, 0, 0.2);
            padding: 20px;
            border-radius: 4px;
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.4);
        }
        .panel.alert {
            border-color: var(--neon-red);
            box-shadow: 0 0 15px rgba(255, 0, 51, 0.3);
        }
        .panel.alert:hover {
            box-shadow: 0 0 25px rgba(255, 0, 51, 0.5);
        }
        .panel h2 {
            font-size: 1.3em;
            margin-top: 0;
            border-bottom: 1px solid var(--neon-green);
            padding-bottom: 8px;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            letter-spacing: 1px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 0.95em;
        }
        .status.online { color: var(--neon-green); }
        .status.active { color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan); }
        .status.warning { color: var(--neon-yellow); text-shadow: 0 0 5px var(--neon-yellow); }
        
        @keyframes flicker {
            0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100% { opacity: .99; }
            20%, 21.999%, 63%, 63.999%, 65%, 69.999% { opacity: 0.4; }
        }
        .pulse {
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        ul { list-style-type: none; padding-left: 0; margin: 0; }
        li { margin-bottom: 8px; padding: 5px; background: rgba(0,0,0,0.5); border-left: 3px solid transparent; }
        li.online { border-left-color: var(--neon-green); }
        li.active { border-left-color: var(--neon-cyan); }
        li.warning { border-left-color: var(--neon-yellow); }
        
        .icon { margin-right: 8px; filter: drop-shadow(0 0 2px rgba(255,255,255,0.5)); }
        .terminal {
            margin-top: 20px;
            font-size: 0.85em;
            color: var(--neon-magenta);
            background: rgba(20, 0, 20, 0.6);
            padding: 10px;
            border: 1px dashed var(--neon-magenta);
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1><span class="icon">🛰️</span> ORBITAL COMMAND | NUVOLA <span class="icon">🌌</span></h1>
        <p class="pulse">STATUS: ONLINE | SECURE UPLINK ESTABLISHED | ENCRYPTION: QUANTUM-AES-256</p>
        <p class="pulse" style="color: var(--neon-green); font-size: 1.2em; font-weight: bold; margin-top: 15px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li class="status active">
                    <span><span class="icon">🐺</span> SQUADRA_ALPHA (Scalper Binance)</span>
                    <span class="pulse">[ENGAGED]</span>
                </li>
                <li class="status active">
                    <span><span class="icon">⚡</span> SQUADRA_DELTA (Order Flow)</span>
                    <span class="pulse">[SCANNING]</span>
                </li>
                <li class="status online">
                    <span><span class="icon">⚖️</span> SQUADRA_GAMMA (Pairs Bitget)</span>
                    <span>[STANDBY]</span>
                </li>
            </ul>
            <div class="terminal">
                > Alpha_PnL_1h: +1.24% <br>
                > Delta_Order_Imbalance: 68% BUY <br>
                > Gamma_Spread_Target: 0.04% <br>
                > Latency_to_Binance: 12ms
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li class="status active">
                    <span><span class="icon">🕴️</span> Lo Strozzino (Funding Arb)</span>
                    <span class="pulse">[EXTRACTING]</span>
                </li>
                <li class="status online">
                    <span><span class="icon">🧮</span> Il Contabile (DCA)</span>
                    <span>[MONITORING]</span>
                </li>
                <li class="status active">
                    <span><span class="icon">👼</span> L'Angelo Custode (MEV Arbitrum)</span>
                    <span class="pulse">[SHIELDING]</span>
                </li>
            </ul>
            <div class="terminal">
                > Strozzino_APR_Avg: 24.5% <br>
                > Contabile_Next_Buy_Window: 4H 12M <br>
                > Angelo_Custode_Blocks_Won: 12 <br>
                > Trinity_Core: NOMINAL
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel alert">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <ul>
                <li class="status warning">
                    <span><span class="icon">🔮</span> The Oracle (Binance Sentiment)</span>
                    <span>[GREED: 78]</span>
                </li>
                <li class="status active">
                    <span><span class="icon">🐳</span> Whale Tracker</span>
                    <span class="pulse">[TRACKING]</span>
                </li>
            </ul>
            <div class="terminal" style="color: var(--neon-yellow); border-color: var(--neon-yellow);">
                > ALERT: 1400 BTC moved to Coinbase Pro <br>
                > ORACLE_PRED: Long Squeeze Probability 65% <br>
                > VOLATILITY_INDEX: HIGH <br>
                > MARKET_PHASE: DISTRIBUTION
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 50px; font-size: 0.75em; opacity: 0.4;">
        ORBITAL COMMAND SYSTEM v9.9.4 // ROOT ACCESS GRANTED // UNAUTHORIZED CONNECTIONS WILL BE TERMINATED
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000 by default or any other port
    app.run(host='0.0.0.0', port=5000)
