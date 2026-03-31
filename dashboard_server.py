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
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px currentColor;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        h1 { color: var(--neon-blue); text-align: center; border-bottom: 2px solid var(--neon-blue); padding-bottom: 10px; }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, currentColor, transparent);
            opacity: 0.5;
        }
        .panel:hover {
            box-shadow: 0 0 25px rgba(57, 255, 20, 0.4);
            transform: translateY(-2px);
        }
        .panel.trinity { border-color: var(--neon-pink); color: var(--neon-pink); box-shadow: 0 0 15px rgba(255, 0, 255, 0.15); }
        .panel.trinity:hover { box-shadow: 0 0 25px rgba(255, 0, 255, 0.4); }
        .panel.market { border-color: var(--neon-blue); color: var(--neon-blue); box-shadow: 0 0 15px rgba(0, 255, 255, 0.15); }
        .panel.market:hover { box-shadow: 0 0 25px rgba(0, 255, 255, 0.4); }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: currentColor;
            box-shadow: 0 0 10px currentColor;
            animation: pulse 1.5s infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.7; box-shadow: 0 0 0 0 rgba(currentColor, 0.7); }
            70% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 10px rgba(currentColor, 0); }
            100% { transform: scale(0.95); opacity: 0.7; box-shadow: 0 0 0 0 rgba(currentColor, 0); }
        }
        .blink-text { animation: blink 1s infinite alternate; }
        @keyframes blink {
            from { opacity: 0.4; }
            to { opacity: 1; }
        }
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { 
            margin-bottom: 15px; 
            border-bottom: 1px dashed rgba(255,255,255,0.1); 
            padding-bottom: 10px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            font-size: 0.95em;
        }
        li:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
        .stat-value { font-weight: bold; background: rgba(0,0,0,0.5); padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2); }
        
        .matrix-bg {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(rgba(0,0,0,0.9), rgba(0,0,0,0.9)), url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><text x="10" y="50" fill="rgba(57, 255, 20, 0.05)" font-family="monospace">10101</text></svg>');
            z-index: -1;
            pointer-events: none;
        }
    </style>
</head>
<body>
    <div class="matrix-bg"></div>
    <h1>🛰️ ORBITAL COMMAND <span class="blink-text">_NUVOLA</span> 🛰️</h1>
    <p style="text-align: center; font-size: 1.2em;">SYSTEM STATUS: <span class="status-indicator"></span> <b>ONLINE & FULLY OPERATIONAL</b></p>
    <p style="text-align: center; font-size: 1.1em; color: var(--neon-pink); border: 1px dashed var(--neon-pink); padding: 5px 15px; width: fit-content; margin: 10px auto; box-shadow: 0 0 10px rgba(255, 0, 255, 0.3);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <br><small style="font-size:0.5em; opacity:0.7;">HIGH-FREQUENCY TRADING</small></h2>
            <ul>
                <li><span><span class="status-indicator"></span> <b>SQUADRA_ALPHA</b> <br><small>(Binance Scalper)</small></span> <span class="stat-value">ACTIVE [245 ops/h]</span></li>
                <li><span><span class="status-indicator"></span> <b>SQUADRA_DELTA</b> <br><small>(Order Flow / DOM)</small></span> <span class="stat-value">ACTIVE [Scanning]</span></li>
                <li><span><span class="status-indicator"></span> <b>SQUADRA_GAMMA</b> <br><small>(Bitget Pairs)</small></span> <span class="stat-value">ACTIVE [Spread 0.04%]</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY <br><small style="font-size:0.5em; opacity:0.7;">BACKGROUND OPERATIONS</small></h2>
            <ul>
                <li><span><span class="status-indicator"></span> <b>Lo Strozzino</b> <br><small>(Funding Arb)</small></span> <span class="stat-value">ONLINE [APR 18.4%]</span></li>
                <li><span><span class="status-indicator"></span> <b>Il Contabile</b> <br><small>(DCA Engine)</small></span> <span class="stat-value">ONLINE [Next: 4h]</span></li>
                <li><span><span class="status-indicator"></span> <b>L'Angelo Custode</b> <br><small>(MEV Arbitrum)</small></span> <span class="stat-value">ONLINE [Mempool Sync]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📊 METRICHE MERCATO <br><small style="font-size:0.5em; opacity:0.7;">LIVE DATA FEEDS</small></h2>
            <ul>
                <li><span>🔮 <b>The Oracle</b> <br><small>(Binance Sentiment)</small></span> <span class="stat-value">BULLISH [78/100]</span></li>
                <li><span>🐳 <b>Whale Tracker</b> <br><small>(Large Transactions)</small></span> <span class="stat-value">+4,200 BTC IN</span></li>
                <li><span>⚡ <b>Volatility Index</b> <br><small>(VIX Crypto)</small></span> <span class="stat-value blink-text">ELEVATED [HIGH]</span></li>
            </ul>
        </div>
    </div>
    
    <div style="margin-top: 40px; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 15px; font-size: 0.8em; text-align: center; color: #555;">
        <p>SECURE CONNECTION :: NUVOLA MAINNET :: AUTHORIZED PERSONNEL ONLY :: <span id="clock"></span></p>
    </div>

    <script>
        setInterval(() => {
            document.getElementById('clock').innerText = new Date().toISOString();
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Running on standard dashboard port, adjust if needed
    app.run(host='0.0.0.0', port=5000, debug=False)
