from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00ffff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        
        h1, h2, h3 {
            margin-bottom: 10px;
            letter-spacing: 2px;
        }
        
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 40px;
            animation: flicker 4s infinite alternate;
        }
        
        .header h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px #0055ff;
            font-size: 2.5em;
        }
        
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
                text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            }
            20%, 24%, 55% {
                text-shadow: none;
            }
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 30px;
        }
        
        .panel {
            background-color: rgba(17, 17, 17, 0.8);
            border: 1px solid var(--neon-green);
            padding: 25px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15), inset 0 0 10px rgba(57, 255, 20, 0.05);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.1), transparent);
            transform: skewX(-20deg);
            animation: scanline 3s linear infinite;
        }
        
        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }
        
        .panel:hover {
            box-shadow: 0 0 25px rgba(57, 255, 20, 0.4);
            transform: translateY(-2px);
        }
        
        .panel h2 {
            border-bottom: 1px dashed;
            padding-bottom: 10px;
        }
        
        /* Tactical Team Theme */
        .panel.tactical { border-color: var(--neon-blue); color: var(--neon-blue); box-shadow: 0 0 15px rgba(0, 255, 255, 0.2); }
        .panel.tactical h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }
        .panel.tactical .status-blip { background: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); }
        
        /* Trinity Protocol Theme */
        .panel.trinity { border-color: var(--neon-purple); color: var(--neon-purple); box-shadow: 0 0 15px rgba(176, 38, 255, 0.2); }
        .panel.trinity h2 { color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }
        .panel.trinity .status-blip { background: var(--neon-purple); box-shadow: 0 0 8px var(--neon-purple); }
        
        /* Market Metrics Theme */
        .panel.metrics { border-color: var(--neon-red); color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 60, 0.2); }
        .panel.metrics h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-top: 20px; border-bottom: 1px dotted rgba(255,255,255,0.2); padding-bottom: 15px; position: relative; }
        
        .data-label { font-size: 1.1em; font-weight: bold; }
        .data-sub { display: block; font-size: 0.8em; opacity: 0.8; margin-top: 5px; color: #aaa; }
        .data-value { position: absolute; right: 0; top: 0; font-weight: bold; font-size: 1.1em; color: #fff; text-shadow: 0 0 5px #fff; }
        
        .status-blip {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.5; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.5; }
        }
        
        .global-status {
            color: var(--neon-green);
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-green);
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <div class="global-status"><span class="status-blip" style="background:var(--neon-green);box-shadow:0 0 8px var(--neon-green);"></span> SYSTEM NOMINAL // ALL MODULES SECURE</div>
        <div class="global-status" style="margin-top: 10px; color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); font-size: 1.0em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="grid">
        <!-- 1. SQUADRE D'ASSALTO (HFT) -->
        <div class="panel tactical">
            <h2>⚔️ SQUADRE D'ASSALTO [HFT]</h2>
            <ul>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">SQUADRA_ALPHA 🦅</span>
                    <span class="data-sub">Scalper [Binance]</span>
                    <span class="data-value">ACTIVE</span>
                </li>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">SQUADRA_DELTA 🌪️</span>
                    <span class="data-sub">Order Flow Tracker</span>
                    <span class="data-value">ACTIVE</span>
                </li>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">SQUADRA_GAMMA ⚖️</span>
                    <span class="data-sub">Pairs Trading [Bitget]</span>
                    <span class="data-value">ACTIVE</span>
                </li>
            </ul>
        </div>

        <!-- 2. PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">LO STROZZINO 🧛</span>
                    <span class="data-sub">Funding Arb [Perps]</span>
                    <span class="data-value" style="color:#b026ff">ONLINE</span>
                </li>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">IL CONTABILE 🧮</span>
                    <span class="data-sub">DCA Engine</span>
                    <span class="data-value" style="color:#b026ff">DAEMON</span>
                </li>
                <li>
                    <span class="status-blip"></span>
                    <span class="data-label">L'ANGELO CUSTODE 🛡️</span>
                    <span class="data-sub">MEV Protection [Arbitrum]</span>
                    <span class="data-value" style="color:#b026ff">WATCHING</span>
                </li>
            </ul>
        </div>

        <!-- 3. METRICHE DI MERCATO -->
        <div class="panel metrics">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <span class="data-label">THE ORACLE 👁️</span>
                    <span class="data-sub">Binance Sentiment Index</span>
                    <span class="data-value">84 (GREED)</span>
                </li>
                <li>
                    <span class="data-label">WHALE TRACKER 🐋</span>
                    <span class="data-sub">Net Flow 24h</span>
                    <span class="data-value">+1,204 BTC</span>
                </li>
                <li>
                    <span class="data-label">LIQUIDATION RADAR 💥</span>
                    <span class="data-sub">REKT [1H]</span>
                    <span class="data-value">$42.7M</span>
                </li>
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
    # Binding on 0.0.0.0
    app.run(host='0.0.0.0', port=5000)
