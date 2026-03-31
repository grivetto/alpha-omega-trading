import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --neon-orange: #ff7f00;
            --bg-color: #050505;
            --panel-bg: rgba(10, 25, 20, 0.7);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 5px;
            text-transform: uppercase;
            font-size: 2.5em;
            margin-bottom: 50px;
            animation: pulse 3s infinite alternate;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 8px;
            padding: 25px;
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.1), 0 0 15px rgba(57, 255, 20, 0.2);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scan 4s linear infinite;
        }

        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 15px;
            margin-top: 0;
            font-size: 1.4em;
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 20px 0;
            padding: 12px;
            background: rgba(0, 255, 255, 0.05);
            border-left: 4px solid var(--neon-blue);
            transition: all 0.3s ease;
        }

        .status-item:hover {
            background: rgba(0, 255, 255, 0.1);
            transform: translateX(5px);
        }

        .status-active { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .status-standby { color: var(--neon-orange); text-shadow: 0 0 8px var(--neon-orange); font-weight: bold; }
        .status-online { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); font-weight: bold; }
        
        @keyframes pulse {
            0% { opacity: 0.8; text-shadow: 0 0 10px var(--neon-blue); }
            100% { opacity: 1; text-shadow: 0 0 25px var(--neon-blue), 0 0 40px var(--neon-blue); }
        }
        
        @keyframes scan {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .terminal-text {
            font-size: 1em;
            line-height: 1.6;
        }

        .terminal-text p {
            margin: 8px 0;
        }

        .blink {
            animation: blinker 1s linear infinite;
        }
        
        @keyframes blinker {
            50% { opacity: 0; }
        }
        
        .glitch-wrapper {
            position: relative;
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 30px; border: 2px solid var(--neon-green); padding: 15px; border-radius: 8px; background: rgba(57, 255, 20, 0.1); box-shadow: 0 0 15px rgba(57, 255, 20, 0.3); font-size: 1.5em; text-shadow: 0 0 10px var(--neon-green);">
        <span class="blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>🐺 SQUADRA_ALPHA <br><small style="color:#888;">[Binance Scalper]</small></span>
                <span class="status-active blink">[ACTIVE]</span>
            </div>
            <div class="status-item">
                <span>⚡ SQUADRA_DELTA <br><small style="color:#888;">[Order Flow]</small></span>
                <span class="status-standby">[STANDBY]</span>
            </div>
            <div class="status-item">
                <span>⚖️ SQUADRA_GAMMA <br><small style="color:#888;">[Bitget Pairs]</small></span>
                <span class="status-active blink">[ACTIVE]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span>🧛 Lo Strozzino <br><small style="color:#888;">[Funding Arb]</small></span>
                <span class="status-online">[ONLINE]</span>
            </div>
            <div class="status-item">
                <span>🧮 Il Contabile <br><small style="color:#888;">[DCA Engine]</small></span>
                <span class="status-online">[ONLINE]</span>
            </div>
            <div class="status-item">
                <span>👼 L'Angelo Custode <br><small style="color:#888;">[MEV Arbitrum]</small></span>
                <span class="status-online">[ONLINE]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ THE ORACLE & WHALE TRACKER</h2>
            <div class="terminal-text">
                <p style="color: #888;">> initializing oracle stream...</p>
                <p>> [SENTIMENT] Binance Global: <strong style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">BULLISH (87%)</strong></p>
                <p style="color: #888;">> parsing mempool anomalies...</p>
                <p style="color: var(--neon-pink);">> [WHALE ALERT] 12,500 BTC moved to cold storage.</p>
                <p>> [ORDER BOOK] Massive buy wall detected @ 68,000 USDT.</p>
                <p>> system status: <span class="status-active">NOMINAL</span> <span class="blink">_</span></p>
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
    # Riavvio silente della Dashboard Flask (Hostato localmente o pubblico)
    app.run(host='0.0.0.0', port=5000, debug=False)
