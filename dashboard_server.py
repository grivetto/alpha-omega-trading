from flask import Flask, render_template_string

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Orbital Command | Nuvola</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-yellow: #ffff00;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
        }
        body {
            background-color: var(--bg-dark);
            background-image: radial-gradient(circle, rgba(0,243,255,0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue);
            font-size: 2.8em;
            text-transform: uppercase;
            letter-spacing: 4px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            width: 100%;
            text-align: center;
            margin-bottom: 40px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            width: 100%;
            max-width: 1400px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15), inset 0 0 20px rgba(57,255,20,0.05);
            padding: 25px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 1px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: scanline 3s linear infinite;
            opacity: 0.5;
        }
        @keyframes scanline {
            0% { transform: translateY(-10px); }
            100% { transform: translateY(400px); }
        }
        .panel h2 {
            color: var(--neon-pink);
            text-shadow: 0 0 8px var(--neon-pink);
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            font-size: 1.4em;
        }
        .item {
            margin: 15px 0;
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid rgba(57, 255, 20, 0.3);
            padding-bottom: 8px;
            font-size: 1.1em;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            animation: pulse 2s infinite alternate;
        }
        .status-alert {
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
        }
        .status-active {
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
        }
        @keyframes pulse {
            0% { opacity: 0.7; }
            100% { opacity: 1; text-shadow: 0 0 12px var(--neon-green), 0 0 20px var(--neon-green); }
        }
        .terminal-header {
            display: flex;
            justify-content: space-between;
            width: 100%;
            max-width: 1400px;
            font-size: 0.9em;
            color: rgba(57, 255, 20, 0.7);
            margin-bottom: -15px;
            text-transform: uppercase;
        }
    </style>
</head>
<body>
    <div class="terminal-header">
        <span>SYS.SEC: CLR</span>
        <span>AUTH: NUVOLA_ADMIN</span>
        <span>UPLINK: SECURE</span>
    </div>
    <h1>🛰️ ORBITAL COMMAND</h1>
    <div style="width: 100%; max-width: 1400px; text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); font-weight: bold; border: 1px dashed var(--neon-yellow); padding: 10px; background: rgba(255, 255, 0, 0.05);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    <div class="grid">
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item"><span>Alpha (Binance Scalper)</span> <span class="status-online">[ ENGAGED 🎯 ]</span></div>
            <div class="item"><span>Delta (Order Flow)</span> <span class="status-active">[ ACTIVE ⚡ ]</span></div>
            <div class="item"><span>Gamma (Bitget Pairs)</span> <span class="status-online">[ SYNCED 🔄 ]</span></div>
        </div>
        
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div class="item"><span>Lo Strozzino (Funding Arb)</span> <span class="status-online">ONLINE 🟢</span></div>
            <div class="item"><span>Il Contabile (DCA)</span> <span class="status-online">ONLINE 🟢</span></div>
            <div class="item"><span>L'Angelo Custode (MEV)</span> <span class="status-online">ONLINE 🟢</span></div>
        </div>

        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="item"><span>The Oracle (Sentiment)</span> <span class="status-online">BULLISH 📈</span></div>
            <div class="item"><span>Whale Tracker (Flows)</span> <span class="status-alert">WARNING 🐋</span></div>
            <div class="item"><span>Liq. Heatmap</span> <span class="status-active">SCANNING 📡</span></div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML)

if __name__ == '__main__':
    # Running on port 5000 by default
    app.run(host='0.0.0.0', port=5000)
