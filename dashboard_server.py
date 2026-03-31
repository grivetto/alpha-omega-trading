from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-cyan: #00f3ff;
            --neon-magenta: #ff00ff;
            --neon-green: #39ff14;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            color: var(--neon-magenta);
            text-shadow: 0 0 10px var(--neon-magenta), 0 0 20px var(--neon-magenta);
            font-size: 2.5em;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 4px;
            animation: pulse 2s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            width: 100%;
            max-width: 1200px;
            margin-top: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.5);
            border-color: #fff;
        }
        .panel h2 {
            color: var(--neon-green);
            font-size: 1.5em;
            margin-top: 0;
            text-shadow: 0 0 5px var(--neon-green);
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        ul { list-style: none; padding: 0; }
        li { margin: 15px 0; font-size: 1.1em; display: flex; justify-content: space-between; align-items: center;}
        .status { 
            color: var(--neon-green); 
            text-shadow: 0 0 5px var(--neon-green); 
            animation: blink 1.5s infinite;
            font-weight: bold;
        }
        .status.trinity {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
        }
        .metric { 
            color: #fff; 
            font-weight: bold;
            text-shadow: 0 0 3px #fff;
        }
        
        @keyframes pulse {
            0% { text-shadow: 0 0 10px var(--neon-magenta), 0 0 20px var(--neon-magenta); }
            50% { text-shadow: 0 0 20px var(--neon-magenta), 0 0 40px var(--neon-magenta); }
            100% { text-shadow: 0 0 10px var(--neon-magenta), 0 0 20px var(--neon-magenta); }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA // ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; padding: 10px; border: 1px solid var(--neon-magenta); border-radius: 5px; background: rgba(255, 0, 255, 0.1);">
        <span style="font-size: 1.2em; font-weight: bold; color: yellow; text-shadow: 0 0 5px yellow;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li><span>🐺 SQUADRA_ALPHA (Scalper Binance)</span> <span class="status">[ONLINE]</span></li>
                <li><span>🦅 SQUADRA_DELTA (Order Flow)</span> <span class="status">[ONLINE]</span></li>
                <li><span>🦂 SQUADRA_GAMMA (Pairs Bitget)</span> <span class="status">[ONLINE]</span></li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span>🕴️ Lo Strozzino (Funding Arb)</span> <span class="status trinity">[ATTIVO]</span></li>
                <li><span>🧮 Il Contabile (DCA)</span> <span class="status trinity">[ATTIVO]</span></li>
                <li><span>👼 L'Angelo Custode (MEV Arb)</span> <span class="status trinity">[ATTIVO]</span></li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li><span>👁️ The Oracle (Binance Sentiment)</span> <span class="metric">BULLISH 78%</span></li>
                <li><span>🐋 Whale Tracker (Inflow 24h)</span> <span class="metric">+45.2M USDT</span></li>
                <li><span>⚡ Latenza Sistema</span> <span class="metric">12ms</span></li>
            </ul>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
